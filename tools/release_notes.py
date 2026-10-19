# napari-lite: own code
"""Print the CHANGELOG.md section of a version, for its GitHub release.

    python tools/release_notes.py 0.1.0      (or v0.1.0, the tag)

The section is everything under ``## <version>`` up to the next ``## ``
heading, without the heading.  A version without a section, or whose
heading still says it is unreleased, is an error: the release workflow
runs this before it publishes anything, so a tag cannot go out with
empty or draft notes.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

CHANGELOG = Path(__file__).resolve().parent.parent / 'CHANGELOG.md'


def section(version: str, text: str) -> str:
    """The notes of ``version`` (a leading ``v`` is ignored) in ``text``,
    the contents of CHANGELOG.md."""
    version = version.removeprefix('v')
    pattern = (
        rf'^## {re.escape(version)}(?P<rest>[^\n]*)\n(?P<notes>.*?)(?=^## |\Z)'
    )
    match = re.search(pattern, text, re.MULTILINE | re.DOTALL)
    if match is None or match.group('rest')[:1] not in ('', ' '):
        raise ValueError(f'CHANGELOG.md has no section for {version}')
    if 'unreleased' in match.group('rest').lower():
        raise ValueError(
            f'CHANGELOG.md still calls {version} unreleased: drop that '
            'from its heading when releasing it'
        )
    notes = match.group('notes').strip()
    if not notes:
        raise ValueError(f'the CHANGELOG.md section for {version} is empty')
    return notes + '\n'


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print(__doc__, file=sys.stderr)
        return 2
    try:
        notes = section(args[0], CHANGELOG.read_text(encoding='utf-8'))
    except ValueError as e:
        print(e, file=sys.stderr)
        return 1
    sys.stdout.write(notes)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
