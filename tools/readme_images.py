# napari-lite: own code
"""Make the README images: viewer screenshots and the benchmark chart.

    python tools/readme_images.py              # all three
    python tools/readme_images.py chart        # the chart only (no window)
    python tools/readme_images.py viewer 3d    # the screenshots only

The screenshots run the README's own example (the astronaut sample) and
the stent volume in 3D, window on screen, and save the whole window.  The
chart draws the numbers of docs/benchmarks.md with Pillow, so it needs
nothing beyond napari-lite's dependencies.  Output: docs/images/.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / 'docs' / 'images'

# docs/benchmarks.md, measured 2026-10-17: napari-lite and napari at the
# same napari commit, fresh environments, one Windows machine; the ratios
# are the point, not the seconds.  (label, napari-lite, napari, unit, kind)
NUMBERS = [
    ('import the package', 0.01, 0.22, 's', 'time'),
    ('first image (ViewerModel + add_image)', 1.5, 3.3, 's', 'time'),
    ('viewer window shown with an image', 3.7, 6.0, 's', 'time'),
    ('memory with a window shown', 222, 276, 'MB', 'size'),
    ('installed size', 370, 761, 'MB', 'size'),
    ('packages installed', 31, 106, '', 'count'),
    ('direct dependencies', 14, 37, '', 'count'),
]

LITE = (38, 166, 154)  # teal
NAPARI = (190, 196, 204)  # grey
INK = (33, 37, 41)
MUTED = (110, 117, 125)


def pump(seconds: float) -> None:
    from qtpy.QtWidgets import QApplication

    app = QApplication.instance()
    end = time.perf_counter() + seconds
    while time.perf_counter() < end:
        app.processEvents()
        time.sleep(0.02)


def screenshot(
    sample: str,
    path: Path,
    *,
    ndisplay: int = 2,
    size: tuple[int, int] = (1120, 700),
    angles: tuple[float, float, float] | None = None,
    **layer_kwargs,
) -> None:
    """The window with one built-in sample, saved as ``path``."""
    import napari_lite as napari

    viewer = napari.Viewer(title='napari-lite')
    viewer.window.resize(*size)
    (layer,) = viewer.open_sample('napari-lite', sample)
    for name, value in layer_kwargs.items():
        setattr(layer, name, value)
    if ndisplay == 3:
        viewer.dims.ndisplay = 3
        if angles is not None:
            viewer.scene.camera.angles = angles
    pump(2.5)
    viewer.screenshot(str(path), canvas_only=False)
    pump(0.5)
    viewer.close()
    print('wrote', path)


def _font(size: int, bold: bool = False):
    from PIL import ImageFont

    names = (
        ['segoeuib.ttf', 'arialbd.ttf', 'DejaVuSans-Bold.ttf']
        if bold
        else ['segoeui.ttf', 'arial.ttf', 'DejaVuSans.ttf']
    )
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _ratio_text(lite: float, napari: float, kind: str) -> str:
    if kind == 'time':
        ratio = napari / lite
        return (
            f'{ratio:.0f}x faster' if ratio >= 10 else f'{ratio:.1f}x faster'
        )
    less = round((1 - lite / napari) * 100)
    return f'{less}% {"fewer" if kind == "count" else "less"}'


def _value_text(value: float, unit: str) -> str:
    if unit == 's':
        text = f'{value:.2f}' if value < 1 else f'{value:.1f}'
    else:
        text = f'{value:g}'
    return f'{text} {unit}'.strip()


def chart(path: Path, scale: int = 2) -> None:
    """Horizontal bars, napari as the full length, napari-lite beside it."""
    from PIL import Image, ImageDraw

    s = scale
    width, height = 1000 * s, 580 * s
    img = Image.new('RGB', (width, height), 'white')
    draw = ImageDraw.Draw(img)
    title, sub, label, small, big = (
        _font(26 * s, bold=True),
        _font(15 * s),
        _font(16 * s),
        _font(14 * s),
        _font(17 * s, bold=True),
    )

    draw.text((40 * s, 28 * s), 'napari-lite vs napari', fill=INK, font=title)
    draw.text(
        (40 * s, 68 * s),
        'Same napari commit, fresh environments, one Windows machine. '
        'Lower is better; napari is the full bar.',
        fill=MUTED,
        font=sub,
    )
    # legend
    lx, ly = width - 300 * s, 34 * s
    for i, (name, colour) in enumerate(
        (('napari-lite', LITE), ('napari', NAPARI))
    ):
        y = ly + i * 24 * s
        draw.rounded_rectangle(
            (lx, y, lx + 26 * s, y + 14 * s), radius=3 * s, fill=colour
        )
        draw.text((lx + 36 * s, y - 3 * s), name, fill=INK, font=label)

    x0, x1 = 380 * s, width - 250 * s
    bar_h, gap = 15 * s, 4 * s
    top = 122 * s
    row_h = 60 * s
    for i, (name, lite, napari, unit, kind) in enumerate(NUMBERS):
        y = top + i * row_h
        draw.text((40 * s, y + 6 * s), name, fill=INK, font=label)
        # napari: the full bar
        draw.rounded_rectangle(
            (x0, y, x1, y + bar_h), radius=4 * s, fill=NAPARI
        )
        draw.text(
            (x1 + 10 * s, y - 2 * s),
            _value_text(napari, unit),
            fill=MUTED,
            font=small,
        )
        # napari-lite: in proportion
        xl = x0 + max((x1 - x0) * lite / napari, 3 * s)
        yl = y + bar_h + gap
        draw.rounded_rectangle(
            (x0, yl, xl, yl + bar_h), radius=4 * s, fill=LITE
        )
        draw.text(
            (xl + 10 * s, yl - 2 * s),
            _value_text(lite, unit),
            fill=LITE,
            font=small,
        )
        draw.text(
            (width - 150 * s, y + 7 * s),
            _ratio_text(lite, napari, kind),
            fill=LITE,
            font=big,
        )
    draw.text(
        (40 * s, height - 36 * s),
        'Measured 2026-10-17; how, and the CI numbers on three operating '
        'systems, in docs/benchmarks.md.',
        fill=MUTED,
        font=small,
    )
    img.save(path, optimize=True)
    print('wrote', path)


def main(argv: list[str]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    wanted = set(argv) or {'viewer', '3d', 'chart'}
    if 'viewer' in wanted:
        screenshot('astronaut', OUT / 'readme_viewer.png')
    if '3d' in wanted:
        screenshot(
            'stent',
            OUT / 'readme_3d.png',
            ndisplay=3,
            angles=(-10, 30, 65),
            colormap='magma',
            rendering='attenuated_mip',
        )
    if 'chart' in wanted:
        chart(OUT / 'readme_benchmark.png')


if __name__ == '__main__':
    main(sys.argv[1:])
