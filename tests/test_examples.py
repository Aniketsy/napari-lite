# napari-lite: own code
"""The examples run: the canvas-only script and the notebook."""

from __future__ import annotations

import base64
import importlib.util
import runpy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = ROOT / 'examples'
TOOLS = ROOT / 'tools'


def test_canvas_only(qtbot, monkeypatch) -> None:
    """examples/canvas_only.py shows a numpy image in a QtCanvas."""
    import napari_lite.qt
    from napari_lite.qt import QtCanvas

    # the example ends with run(); the test must not block on it
    monkeypatch.setattr(napari_lite.qt, 'run', lambda *a, **k: None)
    namespace = runpy.run_path(
        str(EXAMPLES / 'canvas_only.py'), run_name='__main__'
    )
    canvas = namespace['canvas']
    qtbot.addWidget(canvas)
    assert isinstance(canvas, QtCanvas)
    viewer = namespace['viewer']
    assert [layer.name for layer in viewer.layers] == ['noise']
    assert viewer.layers[0] in canvas.layer_to_visual
    assert canvas.windowTitle() == 'napari-lite canvas'
    canvas.close()


@pytest.fixture
def run_notebook():
    """The ``run_notebook`` function of tools/run_notebook.py."""
    spec = importlib.util.spec_from_file_location(
        'run_notebook', TOOLS / 'run_notebook.py'
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.run_notebook


def test_notebook(qtbot, run_notebook) -> None:
    """examples/notebook.ipynb runs through and shows two screenshots."""
    from napari_lite import Viewer

    try:
        notebook = run_notebook(EXAMPLES / 'notebook.ipynb', write=False)
    finally:
        Viewer.close_all()
    cells = [c for c in notebook['cells'] if c['cell_type'] == 'code']
    assert [c['execution_count'] for c in cells] == list(
        range(1, len(cells) + 1)
    )
    printed = ''.join(
        ''.join(o['text'])
        for c in cells
        for o in c['outputs']
        if o['output_type'] == 'stream'
    )
    assert 'import napari_lite:' in printed
    assert 'first image on screen:' in printed
    images = [
        o['data']['image/png']
        for c in cells
        for o in c['outputs']
        if o['output_type'] == 'execute_result' and 'image/png' in o['data']
    ]
    assert len(images) == 2
    for image in images:
        assert base64.b64decode(image)[:8] == b'\x89PNG\r\n\x1a\n'
