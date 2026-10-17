# Releasing napari-lite

Releases are built and published by `.github/workflows/release.yml`.
A version tag publishes to TestPyPI and makes a GitHub release; PyPI is
published only on request, after the napari maintainers have been asked
about the name (backlog issue 25).

## One-time setup

1. In the repository settings on GitHub, create two environments:
   `testpypi` and `pypi`. Give `pypi` a required reviewer so that a PyPI
   publish waits for approval.
2. On [test.pypi.org](https://test.pypi.org) and, later,
   [pypi.org](https://pypi.org), add a *trusted publisher* for the
   project `napari-lite`: owner `Aniketsy`, repository `napari-lite`,
   workflow `release.yml`, environment `testpypi` or `pypi`. No API token
   is stored anywhere.

## Every release

1. Write the version's section in `CHANGELOG.md` and set `version` in
   `pyproject.toml` (the workflow refuses a tag that does not match it).
2. Make sure CI is green on `main`, then commit and tag:

   ```
   git commit -am "Release 0.1.0"
   git tag v0.1.0
   git push origin main v0.1.0
   ```

3. The `Release` workflow builds the sdist and the wheel, checks them with
   `twine check`, installs the wheel and imports it without napari,
   publishes to TestPyPI and creates the GitHub release with the files
   attached. Check the install:

   ```
   pip install -i https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple "napari-lite[pyqt6]==0.1.0"
   ```

4. To publish the same build on PyPI: *Actions > Release > Run workflow*
   on the tag, with target `pypi`. To build without publishing, run it
   with target `none`.

5. Afterwards set `version` to the next `.dev0` and open the next section
   in `CHANGELOG.md`.
