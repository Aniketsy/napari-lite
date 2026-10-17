# napari-lite: own code
"""Run a notebook's code cells without Jupyter; with ``--write``, store
their outputs in the file.

Used by ``tests/test_examples.py`` and to refresh the stored outputs of
``examples/notebook.ipynb``::

    python tools/run_notebook.py examples/notebook.ipynb --write

Cells run in one namespace, as in a kernel.  Magics (``%gui qt``) are
skipped.  A cell's last expression is displayed the way Jupyter does it:
its ``_repr_png_`` becomes an ``image/png`` output.  Printed text becomes a
``stream`` output.
"""

from __future__ import annotations

import argparse
import ast
import base64
import contextlib
import io
import json
import sys
from pathlib import Path
from typing import Any

PNG_HEADER = b'\x89PNG\r\n\x1a\n'


def _strip_magics(source: str) -> str:
    return '\n'.join(
        line
        for line in source.splitlines()
        if not line.lstrip().startswith(('%', '!'))
    )


def run_cell(
    code: str, namespace: dict[str, Any], filename: str
) -> tuple[str, Any]:
    """Execute ``code``; return what it printed and the value of its last
    expression (``None`` when the cell ends in a statement)."""
    tree = ast.parse(code, filename)
    last: ast.Expression | None = None
    if tree.body and isinstance(tree.body[-1], ast.Expr):
        last = ast.Expression(tree.body.pop().value)
    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        exec(compile(tree, filename, 'exec'), namespace)
        value = (
            eval(compile(last, filename, 'eval'), namespace)
            if last is not None
            else None
        )
    return stdout.getvalue(), value


def _outputs(text: str, value: Any, count: int) -> list[dict[str, Any]]:
    outputs: list[dict[str, Any]] = []
    if text:
        outputs.append(
            {
                'output_type': 'stream',
                'name': 'stdout',
                'text': text.splitlines(keepends=True),
            }
        )
    if value is not None:
        # a stable text form: the repr of a display object carries its
        # memory address, which would change the file on every run
        data: dict[str, Any] = {
            'text/plain': [
                f'<{type(value).__module__}.{type(value).__name__}>'
            ]
        }
        png = getattr(value, '_repr_png_', None)
        if png is not None:
            raw = png()
            if raw[:8] != PNG_HEADER:
                raise ValueError('_repr_png_ did not return a PNG')
            data['image/png'] = base64.b64encode(raw).decode('ascii')
        outputs.append(
            {
                'output_type': 'execute_result',
                'data': data,
                'metadata': {},
                'execution_count': count,
            }
        )
    return outputs


def run_notebook(path: str | Path, *, write: bool = False) -> dict[str, Any]:
    """Run every code cell of the notebook at ``path`` and return the
    notebook dict with ``outputs`` and ``execution_count`` filled in;
    with ``write``, also save it back to ``path``."""
    path = Path(path)
    notebook = json.loads(path.read_text(encoding='utf-8'))
    namespace: dict[str, Any] = {'__name__': '__main__'}
    count = 0
    for cell in notebook['cells']:
        if cell['cell_type'] != 'code':
            continue
        count += 1
        code = _strip_magics(''.join(cell['source']))
        text, value = run_cell(code, namespace, f'{path.name}:cell{count}')
        cell['execution_count'] = count
        cell['outputs'] = _outputs(text, value, count)
    if write:
        path.write_text(
            json.dumps(notebook, indent=1, ensure_ascii=False) + '\n',
            encoding='utf-8',
        )
    return notebook


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('notebook', type=Path)
    parser.add_argument(
        '--write',
        action='store_true',
        help='store the outputs in the notebook file',
    )
    args = parser.parse_args(argv)
    notebook = run_notebook(args.notebook, write=args.write)
    cells = [c for c in notebook['cells'] if c['cell_type'] == 'code']
    images = sum(
        'image/png' in o.get('data', {}) for c in cells for o in c['outputs']
    )
    print(
        f'{args.notebook}: {len(cells)} code cells ran, {images} image(s)'
        + (', outputs stored' if args.write else '')
    )
    return 0


if __name__ == '__main__':
    sys.exit(main())
