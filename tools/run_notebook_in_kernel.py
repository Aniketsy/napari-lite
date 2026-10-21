# napari-lite: own code
"""Run a notebook in a real Jupyter kernel, cell by cell, and fail on the
first error.

    python tools/run_notebook_in_kernel.py examples/jupyter.ipynb

Needs nbclient and ipykernel (``pip install nbclient ipykernel``), which
are not napari-lite dependencies.  ``tools/run_notebook.py`` runs a
notebook's code in this process; this one goes through a kernel, so the
pieces an in-process run cannot see get exercised: the widget comms, the
frames the notebook canvas streams, and the kernel's threads.  CI runs it
on Linux, where the canvas is drawn on EGL with no Qt in the kernel.
"""

from __future__ import annotations

import sys
from pathlib import Path


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print(__doc__)
        return 2
    import nbformat
    from nbclient import NotebookClient

    path = Path(argv[0])
    notebook = nbformat.read(path, as_version=4)
    client = NotebookClient(
        notebook,
        timeout=300,
        kernel_name='python3',
        resources={'metadata': {'path': str(path.parent)}},
    )
    client.execute()
    code_cells = [c for c in notebook.cells if c.cell_type == 'code']
    errors = [
        output
        for cell in code_cells
        for output in cell.get('outputs', ())
        if output.get('output_type') == 'error'
    ]
    if errors:  # nbclient raises on errors; this is the belt to its braces
        print(errors[0].get('evalue', 'error'), file=sys.stderr)
        return 1
    print(f'{path}: {len(code_cells)} code cells ran in a kernel')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
