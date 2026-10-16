# Resyncing napari-lite with napari

napari code reaches this repo only through `tools/vendor.py`, only on the
`vendor` branch. `main` is `vendor` plus napari-lite's own code. Upstream
updates arrive by merging `vendor` into `main`, so git does the three-way
merge between napari's changes and ours.

## Rules

1. **Never edit files on `vendor` by hand.** The only commits on `vendor` are
   produced by the routine below. Never run `vendor.py` on `main`.
2. **Shim before edit.** When copied code imports something napari-lite does
   not have, write a small own-code module at the same import path (listed in
   `app_modules` in `tools/vendor.toml`) instead of editing the callers.
3. **Edits to copied files stay small** and carry a `# napari-lite:` comment
   saying why. If an edit can be expressed as a text substitution, put it in
   `literal_rewrites` in `vendor.toml` so it is reapplied on every resync.
4. **Own files start with `# napari-lite: own code`** on the first line. The
   tool never overwrites them. If an own file replaces a *copied* path (for
   example `utils/__init__.py`), also add its module name to `own_modules` in
   `vendor.toml`, so the tool stops copying napari's version.
5. `tools/vendor.toml` and `tools/vendor.py` are developed on `main` like any
   other code; the routine copies them onto `vendor` before running.

## Routine

```bash
# 0. a napari checkout next to this repo, at the commit you want
git -C ../napari fetch origin
git -C ../napari checkout <new-sha>

# 1. on main: bump the pin, look at what changes
#    (edit pin = "<new-sha>" in tools/vendor.toml)
python tools/vendor.py --napari ../napari --diff     # crossings/modules vs VENDORED.json
git commit -am "vendor.toml: pin napari <new-sha>"

# 2. on vendor: bring the tool over, run it, commit the copy
git switch vendor
git checkout main -- tools/
python tools/vendor.py --napari ../napari
git add -A
git commit -m "vendor: napari <new-sha>"

# 3. on main: merge, resolve, test
git switch main
git merge vendor
#   conflicts: ours = napari-lite's edit, theirs = napari's new version.
#   Keep both intents; if the same file conflicts every month, replace the
#   edit with a shim or a literal_rewrites rule (rule 3).
QT_QPA_PLATFORM=offscreen pytest tests src/napari_lite
```

In the pull request, paste the `--diff` output: new or removed crossings
mean napari started (or stopped) using an app module somewhere in the core,
and a shim may need a new name.

## Weekly report

`.github/workflows/upstream-report.yml` runs `vendor.py --diff` against
napari's `main` every Monday and opens an issue when the crossing list or
the copied-module list changed. Nothing is merged automatically.

## Dry run

To check that a resync merges before doing it for real:

```bash
git switch -c vendor-dryrun vendor
git checkout main -- tools/
python tools/vendor.py --napari ../napari --allow-unpinned
git add -A && git commit -m "dry run"
git switch -c main-dryrun main
git merge vendor-dryrun            # must be clean, or show only expected conflicts
git switch main && git branch -D main-dryrun vendor-dryrun
```
