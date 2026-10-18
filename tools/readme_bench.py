# napari-lite: own code
"""Write the README's benchmark table from the Benchmarks workflow's numbers.

    python tools/readme_bench.py                  # latest successful run
    python tools/readme_bench.py --run 39011278624
    python tools/readme_bench.py --results DIR    # JSON files already on disk
    python tools/readme_bench.py --print          # show the block, leave README

The run's artifacts are downloaded with the GitHub CLI (``gh``, logged in).
The Linux numbers of napari-lite and napari go into the block between
``<!-- bench-table -->`` and ``<!-- /bench-table -->`` in README.md: a
caption naming the run, the commit and the napari version, then the table.
Rows whose measurement the run does not have are left out.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / 'README.md'
START, END = '<!-- bench-table -->', '<!-- /bench-table -->'
REPO = 'Aniketsy/napari-lite'

sys.path.insert(0, str(ROOT / 'bench'))
from make_table import load  # noqa: E402

# (kind, key, label): kind picks the record field and the wording of the
# last column
ROWS = [
    ('seconds', 'import', '`import` the package'),
    ('seconds', 'first_image', 'first image (`ViewerModel` + `add_image`)'),
    (
        'seconds',
        'first_frame',
        'viewer window with an image, to its first frame',
    ),
    (
        'seconds',
        'first_labels_layer',
        'first Labels layer, on top of an image',
    ),
    ('per_step', 'slice_step', 'slice step through a 3D image (CPU per step)'),
    ('rss_mb', 'viewer_shown', 'memory with a window shown'),
    ('size_mb', 'size_mb', 'installed size'),
    ('count', 'package_count', 'packages installed'),
    ('count', 'direct_dependencies', 'direct dependencies'),
]


def _value(record: dict, kind: str, key: str):
    if kind in ('seconds', 'per_step', 'rss_mb'):
        field = 'rss_mb' if kind == 'rss_mb' else 'seconds'
        return (record.get(field) or {}).get(key)
    return record.get(key)


def _cell(kind: str, value) -> str:
    if kind == 'seconds':
        return f'{value:.2f} s'
    if kind == 'per_step':
        return f'{value * 1000:.1f} ms'
    if kind in ('rss_mb', 'size_mb'):
        return f'{value:.0f} MB'
    return f'{value:,}'


def _advantage(kind: str, lite: float, nap: float) -> str:
    """The last column: how much lighter or faster napari-lite is."""
    if kind in ('seconds', 'per_step'):
        if abs(nap - lite) <= 0.05 * max(nap, lite):
            return 'same'
        return (
            f'{nap / lite:.1f}x faster'
            if nap > lite
            else f'{lite / nap:.1f}x slower'
        )
    word = 'fewer' if kind == 'count' else 'less'
    if nap <= lite:
        return 'same' if nap == lite else f'{(lite - nap) / nap:.0%} more'
    return f'{(nap - lite) / nap:.0%} {word}'


def table(lite: dict, nap: dict) -> list[str]:
    lines = ['| | napari-lite | napari | |', '|---|---|---|---|']
    for kind, key, label in ROWS:
        a, b = _value(lite, kind, key), _value(nap, kind, key)
        if a is None or b is None:
            continue
        lines.append(
            f'| {label} | {_cell(kind, a)} | {_cell(kind, b)} |'
            f' {_advantage(kind, a, b)} |'
        )
    return lines


def caption(lite: dict, nap: dict, run: dict | None) -> str:
    python = lite.get('python') or nap.get('python') or ''
    repeat = lite.get('repeat') or nap.get('repeat')
    napari_version = nap.get('version')
    parts = ['GitHub Actions, Linux (`ubuntu-latest`)']
    if python:
        parts[0] += f', Python {python}'
    where = (
        f'napari-lite at commit `{run["headSha"][:7]}`'
        if run
        else 'napari-lite at the commit of the run'
    )
    against = (
        f'napari {napari_version} from PyPI'
        if napari_version
        else 'napari from PyPI'
    )
    text = (
        f'{", ".join(parts)}: {where} against {against}, each'
        ' `pip install <package>[pyqt6]` into a fresh environment'
    )
    if repeat:
        text += f', best of {repeat} fresh interpreters'
    text += '.'
    if run:
        day = run.get('createdAt', '')[:10]
        text += f' [Run {run["databaseId"]}]({run["url"]}), {day}.'
    text += (
        ' macOS and Windows, the spread, and how each row is measured:'
        ' [docs/benchmarks.md](docs/benchmarks.md).'
    )
    return text


def block(lite: dict, nap: dict, run: dict | None) -> str:
    return '\n'.join(
        [START, caption(lite, nap, run), '', *table(lite, nap), END]
    )


def replace_block(text: str, new_block: str) -> str:
    start, end = text.find(START), text.find(END)
    if start < 0 or end < 0:
        raise SystemExit(f'README.md has no {START} ... {END} block')
    return text[:start] + new_block + text[end + len(END) :]


def gh(*args: str) -> str:
    proc = subprocess.run(
        ['gh', *args], capture_output=True, text=True, check=False
    )
    if proc.returncode != 0:
        raise SystemExit(f'gh {" ".join(args)} failed: {proc.stderr.strip()}')
    return proc.stdout


def latest_run() -> dict:
    runs = json.loads(
        gh(
            'run',
            'list',
            '--repo',
            REPO,
            '--workflow',
            'bench.yml',
            '--status',
            'success',
            '--limit',
            '1',
            '--json',
            'databaseId,headSha,createdAt,url',
        )
    )
    if not runs:
        raise SystemExit('no successful Benchmarks run on GitHub')
    return runs[0]


def run_info(run_id: str) -> dict:
    return json.loads(
        gh(
            'run',
            'view',
            run_id,
            '--repo',
            REPO,
            '--json',
            'databaseId,headSha,createdAt,url',
        )
    )


def linux_records(results_dir: Path) -> tuple[dict, dict]:
    paths = [str(p) for p in results_dir.rglob('*.json')]
    if not paths:
        raise SystemExit(f'no JSON files under {results_dir}')
    packages = load(paths).get('Linux', {})
    lite, nap = packages.get('napari_lite'), packages.get('napari')
    if not lite or not nap:
        raise SystemExit('the results have no Linux numbers for both packages')
    return lite, nap


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--run', metavar='ID', help='a Benchmarks run id')
    parser.add_argument(
        '--results', metavar='DIR', help='JSON files already downloaded'
    )
    parser.add_argument(
        '--print', action='store_true', help='print the block, keep README.md'
    )
    args = parser.parse_args(argv)

    run = None
    if args.results:
        lite, nap = linux_records(Path(args.results))
    else:
        run = run_info(args.run) if args.run else latest_run()
        with tempfile.TemporaryDirectory() as tmp:
            gh(
                'run',
                'download',
                str(run['databaseId']),
                '--repo',
                REPO,
                '--dir',
                tmp,
            )
            lite, nap = linux_records(Path(tmp))
    new_block = block(lite, nap, run)
    if args.print:
        print(new_block)
        return 0
    text = README.read_text(encoding='utf-8')
    README.write_text(
        replace_block(text, new_block), encoding='utf-8', newline='\n'
    )
    print(
        f'README.md: benchmark table written ({len(table(lite, nap)) - 2} rows)'
    )
    return 0


if __name__ == '__main__':
    sys.exit(main())
