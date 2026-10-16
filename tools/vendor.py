# napari-lite: own code
"""Copy the napari core into ``src/napari_lite`` and report every crossing
into napari's application code.

Usage
-----
    python tools/vendor.py --napari ../napari            # copy + VENDORED.json
    python tools/vendor.py --napari ../napari --report   # only print the report
    python tools/vendor.py --napari ../napari --check    # fail if the pin differs

The tool reads ``tools/vendor.toml``:

* ``pin``          the napari commit the copy is taken from (checked, not
                   checked out: do that yourself with ``git -C ../napari
                   checkout <pin>``)
* ``roots``        modules the crawl starts from
* ``app_modules``  module prefixes that are *not* copied; every import of one
                   is recorded as a crossing. napari-lite provides its own
                   module at the same import path ("shim at the same path").
* ``extra_modules`` modules copied in addition to what the crawl reaches
* ``data``         non-Python files to copy (globs relative to ``src/napari``)
* ``literal_rewrites`` ``{"from x import": "from y import"}`` text
                   substitutions applied to every copied file after the
                   ``napari`` -> ``napari_lite`` rewrite.

Crawling starts at ``roots`` and follows every absolute ``napari.*`` import
(napari forbids relative imports) plus the submodule names given to
``lazy_loader.attach``.  Imports under ``if TYPE_CHECKING:`` are followed but
never count as crossings.  Test files (``_tests/test_*.py``) of a copied
package are copied when every napari module they import is either copied
or an app module.

Files that start with ``# napari-lite: own code`` are never overwritten.
"""

from __future__ import annotations

import argparse
import ast
import fnmatch
import json
import re
import shutil
import subprocess
import sys
import tomllib
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
CONFIG = HERE / 'vendor.toml'
OWN_CODE_MARKER = '# napari-lite: own code'
SRC_PKG = 'napari'
DST_PKG = 'napari_lite'

# ``napari.`` followed by a module-ish name, but not a URL / file suffix.
_MODULE_REF = re.compile(
    r'(?<![\w.])napari(?=\.(?!org\b|io\b|com\b|hub\b|yaml\b|manifest\b)'
    r'[A-Za-z_])'
)
# ``import napari`` / ``import napari as x`` (nothing module-ish after it)
_IMPORT_PKG = re.compile(r'\bimport napari\b(?![\w.-])')
# ``from napari import x``
_FROM_PKG = re.compile(r'\bfrom napari import\b')


@dataclass
class Module:
    name: str
    path: Path
    imports: set[str] = field(default_factory=set)
    type_only_imports: set[str] = field(default_factory=set)
    lazy_imports: set[str] = field(default_factory=set)  # inside a function
    third_party: set[str] = field(default_factory=set)
    lines: int = 0


@dataclass
class Config:
    pin: str
    roots: list[str]
    app_modules: list[str]
    extra_modules: list[str]
    data: list[str]
    literal_rewrites: dict[str, str]
    skip_modules: list[str]
    own_modules: list[str]

    @classmethod
    def load(cls, path: Path) -> Config:
        raw = tomllib.loads(path.read_text(encoding='utf-8'))
        return cls(
            pin=raw['pin'],
            roots=list(raw.get('roots', [])),
            app_modules=list(raw.get('app_modules', [])),
            extra_modules=list(raw.get('extra_modules', [])),
            data=list(raw.get('data', [])),
            literal_rewrites=dict(raw.get('literal_rewrites', {})),
            skip_modules=list(raw.get('skip_modules', [])),
            own_modules=list(raw.get('own_modules', [])),
        )


# --------------------------------------------------------------------------
# module discovery
# --------------------------------------------------------------------------


def discover(src: Path) -> dict[str, Module]:
    """Map every ``napari.*`` module name to its file."""
    modules: dict[str, Module] = {}
    for path in sorted(src.rglob('*.py')):
        rel = path.relative_to(src.parent).with_suffix('')
        parts = list(rel.parts)
        if parts[-1] == '__init__':
            parts = parts[:-1]
        name = '.'.join(parts)
        modules[name] = Module(name=name, path=path)
    return modules


def is_test_module(name: str) -> bool:
    parts = name.split('.')
    return '_tests' in parts or parts[-1] == 'conftest'


def _attach_submodules(tree: ast.AST, package: str) -> set[str]:
    """Submodules named in ``lazy_loader.attach(__name__, [...], {...})``."""
    found: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        fname = (
            func.attr
            if isinstance(func, ast.Attribute)
            else getattr(func, 'id', '')
        )
        if fname not in {'attach', '_attach', 'attach_stub'}:
            continue
        literals = list(node.args[1:]) + [kw.value for kw in node.keywords]
        for lit in literals:
            try:
                value = ast.literal_eval(lit)
            except (ValueError, TypeError):
                continue
            names = value.keys() if isinstance(value, dict) else value
            if not isinstance(names, (list, tuple, set, type({}.keys()))):
                continue
            for sub in names:
                if isinstance(sub, str):
                    found.add(f'{package}.{sub}')
    return found


def parse_module(mod: Module, all_names: set[str]) -> None:
    """Fill ``mod.imports`` / ``type_only_imports`` / ``third_party``."""
    text = mod.path.read_text(encoding='utf-8')
    mod.lines = text.count('\n') + (not text.endswith('\n') and bool(text))
    tree = ast.parse(text, filename=str(mod.path))
    package = mod.name if mod.path.name == '__init__.py' else None

    def visit(node: ast.AST, type_only: bool, lazy: bool) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.If) and _is_type_checking(child.test):
                for sub in child.body:
                    visit(sub, True, lazy)
                for sub in child.orelse:
                    visit(sub, type_only, lazy)
                continue
            if isinstance(child, ast.Import):
                for alias in child.names:
                    _record(alias.name, type_only, lazy)
            elif isinstance(child, ast.ImportFrom):
                base = child.module or ''
                if child.level:  # relative import (only in napari._vendor)
                    pkg_parts = mod.name.split('.')
                    if mod.path.name != '__init__.py':
                        pkg_parts = pkg_parts[:-1]
                    pkg_parts = pkg_parts[: len(pkg_parts) - child.level + 1]
                    base = '.'.join([*pkg_parts, base] if base else pkg_parts)
                if base == SRC_PKG or base.startswith(SRC_PKG + '.'):
                    # ``from napari.x import y``: y may be a submodule
                    for alias in child.names:
                        full = f'{base}.{alias.name}'
                        _record(
                            full if full in all_names else base,
                            type_only,
                            lazy,
                        )
                else:
                    _record(base, type_only, lazy)
            in_function = isinstance(
                child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)
            )
            visit(child, type_only, lazy or in_function)

    eager_imports: set[str] = set()

    def _record(name: str, type_only: bool, lazy: bool) -> None:
        top = name.split('.')[0]
        if top == SRC_PKG:
            resolved = _resolve(name, all_names)
            if type_only:
                mod.type_only_imports.add(resolved)
            else:
                mod.imports.add(resolved)
                (mod.lazy_imports if lazy else eager_imports).add(resolved)
        elif top and not type_only:
            mod.third_party.add(top)

    visit(tree, False, False)
    if package:
        mod.imports |= {
            n for n in _attach_submodules(tree, package) if n in all_names
        }
    # a module always needs its parent packages (``__init__`` runs first)
    parts = mod.name.split('.')
    for i in range(1, len(parts)):
        parent = '.'.join(parts[:i])
        if parent in all_names and parent != mod.name:
            mod.imports.add(parent)
    mod.imports.discard(mod.name)
    mod.type_only_imports -= mod.imports
    mod.type_only_imports.discard(mod.name)
    # an import is lazy only if *every* import of it sits inside a function
    mod.lazy_imports -= eager_imports


def _is_type_checking(test: ast.AST) -> bool:
    if isinstance(test, ast.Name):
        return test.id == 'TYPE_CHECKING'
    if isinstance(test, ast.Attribute):
        return test.attr == 'TYPE_CHECKING'
    return False


def _resolve(name: str, all_names: set[str]) -> str:
    """``napari.a.b.C`` -> longest prefix that is a real module."""
    parts = name.split('.')
    while parts and '.'.join(parts) not in all_names:
        parts.pop()
    return '.'.join(parts) if parts else name


# --------------------------------------------------------------------------
# crawl
# --------------------------------------------------------------------------


def matches(name: str, prefixes: list[str]) -> str | None:
    """Return the matching prefix if ``name`` is ``prefix`` or below it."""
    for prefix in prefixes:
        if name == prefix or name.startswith(prefix + '.'):
            return prefix
    return None


@dataclass
class Result:
    copied: dict[str, Module]
    crossings: dict[
        str, list[tuple[str, str]]
    ]  # app module -> (importer, kind)
    tests: dict[str, Module]
    skipped_tests: dict[str, list[str]]
    missing: dict[str, list[str]]


def crawl(modules: dict[str, Module], cfg: Config) -> Result:
    all_names = set(modules)
    for mod in modules.values():
        parse_module(mod, all_names)

    copied: dict[str, Module] = {}
    crossings: dict[str, list[tuple[str, str]]] = defaultdict(list)
    missing: dict[str, list[str]] = defaultdict(list)
    queue = [*cfg.roots, *cfg.extra_modules]
    for name in queue:
        if name not in modules:
            sys.exit(f'vendor.toml names an unknown module: {name}')

    while queue:
        name = queue.pop()
        if name in copied or is_test_module(name):
            continue
        if matches(name, cfg.skip_modules) or name in cfg.own_modules:
            continue
        app = matches(name, cfg.app_modules)
        if app and name not in cfg.roots and name not in cfg.extra_modules:
            continue
        mod = modules[name]
        copied[name] = mod
        for dep in sorted(mod.imports | mod.type_only_imports):
            if dep in mod.type_only_imports:
                kind = 'type'
            elif dep in mod.lazy_imports:
                kind = 'lazy'
            else:
                kind = 'eager'
            if dep not in modules:
                missing[dep].append(name)
                continue
            if dep in cfg.own_modules:  # napari-lite provides this file
                continue
            if matches(dep, cfg.skip_modules):
                continue
            app = matches(dep, cfg.app_modules)
            if app:
                crossings[app].append((name, kind))
                continue
            if dep not in copied:
                queue.append(dep)

    tests: dict[str, Module] = {}
    skipped_tests: dict[str, list[str]] = {}
    copied_packages = {
        name for name in copied if modules[name].path.name == '__init__.py'
    }
    for name, mod in modules.items():
        if not is_test_module(name) or name.endswith('.conftest'):
            continue
        package = name.rsplit('._tests', 1)[0]
        if package not in copied_packages:
            continue
        if any(matches(name, [t]) for t in cfg.skip_modules):
            continue
        blockers = sorted(
            dep
            for dep in mod.imports
            if dep not in copied
            and dep not in cfg.own_modules
            and not matches(dep, cfg.app_modules)
            and not dep.startswith(f'{package}._tests')
        )
        if blockers:
            skipped_tests[name] = blockers
        else:
            tests[name] = mod
    return Result(copied, dict(crossings), tests, skipped_tests, dict(missing))


def why(result: Result, cfg: Config, target: str) -> list[str]:
    """Shortest runtime-import chain from a root to ``target`` (BFS)."""
    parents: dict[str, str | None] = dict.fromkeys(cfg.roots)
    queue = list(cfg.roots)
    while queue:
        name = queue.pop(0)
        if name == target:
            chain = [name]
            while parents[chain[-1]] is not None:
                chain.append(parents[chain[-1]])  # type: ignore[arg-type]
            return chain[::-1]
        mod = result.copied.get(name)
        if mod is None:
            continue
        for dep in sorted(mod.imports):
            if dep not in parents and (dep in result.copied or dep == target):
                parents[dep] = name
                queue.append(dep)
    return []


# --------------------------------------------------------------------------
# writing
# --------------------------------------------------------------------------


def rewrite(text: str, literal: dict[str, str]) -> str:
    text = _FROM_PKG.sub(f'from {DST_PKG} import', text)
    text = _IMPORT_PKG.sub(f'import {DST_PKG}', text)
    text = _MODULE_REF.sub(DST_PKG, text)
    for old, new in literal.items():
        text = text.replace(old, new)
    return text


def is_own_code(path: Path) -> bool:
    if not path.exists():
        return False
    with path.open(encoding='utf-8') as fh:
        return fh.readline().rstrip() == OWN_CODE_MARKER


def write_tree(
    src: Path, dst: Path, result: Result, cfg: Config
) -> tuple[list[str], list[str]]:
    """Write copied modules; return (written, kept_own_code) relative paths."""
    written: list[str] = []
    kept: list[str] = []
    wanted: set[Path] = set()
    for mod in [*result.copied.values(), *result.tests.values()]:
        rel = mod.path.relative_to(src)
        target = dst / rel
        wanted.add(target)
        if is_own_code(target):
            kept.append(rel.as_posix())
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        text = mod.path.read_text(encoding='utf-8')
        target.write_text(
            rewrite(text, cfg.literal_rewrites),
            encoding='utf-8',
            newline='\n',
        )
        written.append(rel.as_posix())
    # test packages need an __init__.py if napari has one
    for test_mod in result.tests.values():
        init = test_mod.path.parent / '__init__.py'
        rel = init.relative_to(src)
        if init.exists() and (dst / rel) not in wanted:
            (dst / rel).parent.mkdir(parents=True, exist_ok=True)
            (dst / rel).write_text(
                rewrite(
                    init.read_text(encoding='utf-8'), cfg.literal_rewrites
                ),
                encoding='utf-8',
                newline='\n',
            )
            wanted.add(dst / rel)
            written.append(rel.as_posix())
    # data files travel with their package: copied only if that is copied
    copied_dirs = {m.path.parent for m in result.copied.values()}

    def owner_copied(path: Path) -> bool:
        for folder in [path.parent, *path.parents]:
            if folder == src:
                return False
            if folder in copied_dirs:
                return True
        return False

    for pattern in cfg.data:
        for path in sorted(src.glob(pattern)):
            if path.is_dir() or not owner_copied(path):
                continue
            rel = path.relative_to(src)
            target = dst / rel
            wanted.add(target)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
            written.append(rel.as_posix())
    # remove copied files that are no longer wanted (never own code)
    for path in sorted(dst.rglob('*')):
        if path.is_dir() or path in wanted or is_own_code(path):
            continue
        if path.suffix == '.py' or any(
            fnmatch.fnmatch(path.relative_to(dst).as_posix(), p)
            for p in cfg.data
        ):
            path.unlink()
    for path in sorted(dst.rglob('*'), reverse=True):
        if path.is_dir() and not any(path.iterdir()):
            path.rmdir()
    return written, kept


# --------------------------------------------------------------------------
# report
# --------------------------------------------------------------------------


def napari_sha(napari: Path) -> str:
    out = subprocess.run(
        ['git', '-C', str(napari), 'rev-parse', 'HEAD'],
        check=True,
        capture_output=True,
        text=True,
    )
    return out.stdout.strip()


def summary(result: Result, modules: dict[str, Module]) -> dict:
    # app module -> {importer: 'eager' | 'lazy'} (runtime imports only)
    runtime: dict[str, dict[str, str]] = defaultdict(dict)
    type_only: dict[str, set[str]] = defaultdict(set)
    for app, importers in result.crossings.items():
        for importer, kind in importers:
            if kind == 'type':
                type_only[app].add(importer)
            elif runtime[app].get(importer) != 'eager':
                runtime[app][importer] = kind
    for app, importers in type_only.items():
        importers -= set(runtime.get(app, {}))
    by_importer: dict[str, set[str]] = defaultdict(set)
    for app, importers in runtime.items():
        for importer in importers:
            by_importer[importer].add(app)
    third_party: dict[str, list[str]] = defaultdict(list)
    for name, mod in sorted(result.copied.items()):
        for pkg in mod.third_party:
            if pkg not in sys.stdlib_module_names and pkg != '__future__':
                third_party[pkg].append(name)
    third_party_sorted = dict(
        sorted(third_party.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    )
    return {
        'modules_total': sum(1 for n in modules if not is_test_module(n)),
        'modules_copied': len(result.copied),
        'lines_copied': sum(m.lines for m in result.copied.values()),
        'tests_copied': len(result.tests),
        'tests_skipped': dict(sorted(result.skipped_tests.items())),
        'crossings_total': sum(len(v) for v in runtime.values()),
        'app_modules_hit': len(runtime),
        'crossings': {
            app: dict(sorted(importers.items()))
            for app, importers in sorted(
                runtime.items(), key=lambda kv: (-len(kv[1]), kv[0])
            )
        },
        'type_only_crossings': {
            app: sorted(v) for app, v in sorted(type_only.items()) if v
        },
        'importers_with_crossings': {
            k: sorted(v) for k, v in sorted(by_importer.items())
        },
        'third_party_imports': third_party_sorted,
        'missing_modules': result.missing,
    }


def print_report(info: dict) -> None:
    print(
        f'copied {info["modules_copied"]} of {info["modules_total"]} modules '
        f'({info["lines_copied"]:,} lines), {info["tests_copied"]} test files '
        f'({len(info["tests_skipped"])} skipped)'
    )
    print(
        f'{info["crossings_total"]} crossings into '
        f'{info["app_modules_hit"]} app modules '
        f'("lazy" = imported inside a function only):'
    )
    for app, importers in info['crossings'].items():
        print(f'  {len(importers):3d}  {app}')
        for imp, when in importers.items():
            print(f'         <- {imp}{"  (lazy)" if when == "lazy" else ""}')
    if info['type_only_crossings']:
        print('type-checking-only crossings (no runtime cost):')
        for app, importers in info['type_only_crossings'].items():
            print(f'  {app}: {", ".join(importers)}')
    if info['missing_modules']:
        print('imports of modules that do not exist:')
        for name, importers in info['missing_modules'].items():
            print(f'  {name} <- {", ".join(importers)}')
    print('third-party packages (number of copied modules importing them):')
    print(
        '  '
        + ', '.join(
            f'{k} {len(v)}' for k, v in info['third_party_imports'].items()
        )
    )
    rare = {
        k: v for k, v in info['third_party_imports'].items() if len(v) <= 2
    }
    if rare:
        print('  used by at most two modules:')
        for pkg, users in rare.items():
            print(f'    {pkg}: {", ".join(users)}')


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument(
        '--napari',
        type=Path,
        required=True,
        help='path to a napari checkout',
    )
    parser.add_argument(
        '--report', action='store_true', help='print the report, write nothing'
    )
    parser.add_argument(
        '--check',
        action='store_true',
        help='exit 1 if the checkout is not at the pinned commit',
    )
    parser.add_argument(
        '--allow-unpinned',
        action='store_true',
        help='copy even if the checkout is not at the pinned commit',
    )
    parser.add_argument(
        '--why',
        metavar='MODULE',
        action='append',
        default=[],
        help='print the import chain from a root to MODULE (repeatable)',
    )
    parser.add_argument('--config', type=Path, default=CONFIG)
    parser.add_argument('--dest', type=Path, default=REPO / 'src' / DST_PKG)
    args = parser.parse_args(argv)

    cfg = Config.load(args.config)
    napari = args.napari.resolve()
    src = napari / 'src' / SRC_PKG
    if not src.is_dir():
        sys.exit(f'not a napari checkout: {napari}')
    sha = napari_sha(napari)
    pinned = sha.startswith(cfg.pin)
    if args.check:
        print(f'napari at {sha[:12]}, pin {cfg.pin}')
        return 0 if pinned else 1
    read_only = args.report or bool(args.why)
    if not pinned and not read_only and not args.allow_unpinned:
        sys.exit(
            f'napari checkout is at {sha[:12]} but vendor.toml pins {cfg.pin}.\n'
            f'Run `git -C {napari} checkout {cfg.pin}` or pass --allow-unpinned.'
        )

    modules = discover(src)
    result = crawl(modules, cfg)
    info = summary(result, modules)
    if args.why:
        for target in args.why:
            print(
                ' -> '.join(why(result, cfg, target)) or f'{target}: unreached'
            )
        return 0
    if args.report:
        print_report(info)
        return 0

    written, kept = write_tree(src, args.dest, result, cfg)
    manifest = {
        'napari_commit': sha,
        'pin': cfg.pin,
        'roots': cfg.roots,
        'app_modules': cfg.app_modules,
        **info,
        'copied_modules': sorted(result.copied),
        'copied_tests': sorted(result.tests),
        'own_code_kept': kept,
    }
    (REPO / 'VENDORED.json').write_text(
        json.dumps(manifest, indent=2) + '\n',
        encoding='utf-8',
        newline='\n',
    )
    print_report(info)
    print(f'wrote {len(written)} files, kept {len(kept)} own-code files')
    print(f'wrote {REPO / "VENDORED.json"}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
