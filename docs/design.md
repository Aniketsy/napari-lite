# Design decisions

## Data interpretation: the same rules as napari

napari guesses a few things about the data handed to `add_image`:

- **RGB**: an array whose last axis has length 3 or 4, with the two axes
  before it longer than 30, is shown as RGB(A) (`guess_rgb` in
  `layers/image/_image_utils.py`).
- **Multiscale**: a list or tuple of arrays whose shapes decrease is a
  multiscale image (`guess_multiscale`).
- **Labels**: `add_image` never turns integer data into a Labels layer; only
  napari's readers do that (`guess_labels`), and napari-lite has none.
- **Channel axis**: never guessed. `channel_axis=None` means one layer;
  `channel_axis=0` splits the data into one layer per channel.

The discussion in napari issue 5940 asked whether a lite viewer should
drop the guessing and require `rgb=` and `channel_axis=` explicitly.
napari-lite keeps napari's rules unchanged:

- The one-line swap (`import napari_lite as napari`) is the project's main
  promise; a script must give the same layers with both packages, and
  `tests/test_compat_napari.py` checks that.
- The rules live in copied code; changing them would mean editing copied
  files and carrying the diff through every resync.
- The guesses can always be overridden: `rgb=False`, `multiscale=False`,
  `channel_axis=...`.

What napari-lite does *not* do is the guessing that happens outside the
layer code: there are no reader plugins. `viewer.open()` has a built-in
reader for a few formats (png, jpg, bmp, gif, webp, tif, npy, npz:
imageio, numpy, tifffile when installed) that hands every file to
`add_image` as an array, so the rules above apply to opened files too,
and raises `NotImplementedError` for anything else.

The rules are pinned by `tests/test_data_interpretation.py`, which also
compares them with napari where napari is installed.
