# napari-lite: own code
"""tools/release_notes.py: the CHANGELOG.md section a GitHub release
shows, and the checks that keep a tag from going out without one."""

from __future__ import annotations

import importlib.util
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

CHANGELOG = """# Changelog

## 0.2.0 (unreleased)

### Added

- Something new.

## 0.1.0

First release.

### Added

- The viewer.

## 0.0.1

Not this one.
"""


@pytest.fixture(scope='module')
def release_notes():
    spec = importlib.util.spec_from_file_location(
        'release_notes', ROOT / 'tools' / 'release_notes.py'
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_section_of_a_version(release_notes) -> None:
    notes = release_notes.section('0.1.0', CHANGELOG)
    assert notes == 'First release.\n\n### Added\n\n- The viewer.\n'
    assert release_notes.section('v0.1.0', CHANGELOG) == notes  # the tag


def test_no_release_without_finished_notes(release_notes) -> None:
    with pytest.raises(ValueError, match=r'no section for 0\.3\.0'):
        release_notes.section('v0.3.0', CHANGELOG)
    with pytest.raises(ValueError, match=r'still calls 0\.2\.0 unreleased'):
        release_notes.section('0.2.0', CHANGELOG)
    with pytest.raises(ValueError, match=r'no section for 0\.0$'):
        release_notes.section('0.0', CHANGELOG)  # 0.0.1 is another version
    with pytest.raises(ValueError, match='is empty'):
        release_notes.section('1.0.0', '## 1.0.0\n\n## 0.9.0\n\n- x\n')


def test_the_command(release_notes, capsys) -> None:
    assert release_notes.main(['nope']) == 1
    assert 'no section for nope' in capsys.readouterr().err
    assert release_notes.main([]) == 2


def test_the_version_in_pyproject_has_its_notes(release_notes) -> None:
    """A released version (no .dev) needs a finished CHANGELOG.md section;
    the release workflow refuses its tag otherwise."""
    with open(ROOT / 'pyproject.toml', 'rb') as f:
        version = tomllib.load(f)['project']['version']
    if 'dev' in version:
        pytest.skip(f'{version} is a development version')
    text = (ROOT / 'CHANGELOG.md').read_text(encoding='utf-8')
    assert release_notes.section(version, text).strip()
