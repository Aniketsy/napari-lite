# napari-lite: own code
"""File the backlog in ``docs/backlog.md`` as GitHub issues, in order.

    python tools/create_issues.py --dry-run          # show what would be filed
    python tools/create_issues.py                    # file them with ``gh``
    python tools/create_issues.py --from 05          # resume at issue 05

Each ``## NN · Title`` section becomes one issue.  The line right after the
heading gives ``milestone: ... · labels: a, b · depends: {{NN}}, {{MM}}``.
Milestones and labels are created when missing.  ``{{NN}}`` placeholders in
the bodies are replaced by the real issue numbers once every issue exists.
Requires the ``gh`` CLI, logged in, run inside the repository.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

BACKLOG = Path(__file__).resolve().parent.parent / 'docs' / 'backlog.md'
HEADING = re.compile(r'^## (\d{2}) · (.+?)\s*$')
META = re.compile(
    r'^milestone:\s*(?P<milestone>[^·]+?)\s*·\s*labels:\s*(?P<labels>[^·]*?)'
    r'\s*·\s*depends:\s*(?P<depends>.*?)\s*$'
)
PLACEHOLDER = re.compile(r'\{\{(\d{2})\}\}')


@dataclass
class Issue:
    key: str
    title: str
    milestone: str
    labels: list[str]
    depends: list[str]
    body: str
    number: int | None = None


def parse(text: str) -> list[Issue]:
    issues: list[Issue] = []
    current: Issue | None = None
    body: list[str] = []
    for line in text.splitlines():
        m = HEADING.match(line)
        if m:
            if current:
                current.body = '\n'.join(body).strip()
                issues.append(current)
            current = Issue(m.group(1), m.group(2), '', [], [], '')
            body = []
            continue
        if current is None:
            continue
        mm = META.match(line)
        if mm and not current.milestone:
            current.milestone = mm['milestone'].strip()
            current.labels = [
                s.strip() for s in mm['labels'].split(',') if s.strip()
            ]
            current.depends = PLACEHOLDER.findall(mm['depends'])
            continue
        body.append(line)
    if current:
        current.body = '\n'.join(body).strip()
        issues.append(current)
    return issues


def gh(*args: str, capture: bool = True) -> str:
    proc = subprocess.run(
        ['gh', *args], check=True, capture_output=capture, text=True
    )
    return proc.stdout if capture else ''


def ensure_labels(repo: str, labels: set[str], dry_run: bool) -> None:
    existing = {
        item['name']
        for item in json.loads(
            gh('label', 'list', '--repo', repo, '--json', 'name', '-L', '200')
        )
    }
    for label in sorted(labels - existing):
        print(f'create label {label}')
        if not dry_run:
            gh('label', 'create', label, '--repo', repo, '--force')


def ensure_milestones(repo: str, names: list[str], dry_run: bool) -> None:
    existing = {
        item['title']
        for item in json.loads(
            gh('api', f'repos/{repo}/milestones?state=all&per_page=100')
        )
    }
    for name in names:
        if name in existing:
            continue
        print(f'create milestone {name}')
        if not dry_run:
            gh('api', f'repos/{repo}/milestones', '-f', f'title={name}')


def body_with_depends(issue: Issue, numbers: dict[str, int | None]) -> str:
    def number(key: str) -> str:
        n = numbers.get(key)
        return f'#{n}' if n else f'{{{{{key}}}}}'

    body = PLACEHOLDER.sub(lambda m: number(m.group(1)), issue.body)
    if issue.depends:
        deps = ', '.join(number(k) for k in issue.depends)
        body = f'Depends on: {deps}\n\n{body}'
    return body


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--repo', help='owner/name; default: current repo')
    parser.add_argument(
        '--from', dest='start', default='00', help='first key to file'
    )
    args = parser.parse_args(argv)

    repo = (
        args.repo
        or gh(
            'repo', 'view', '--json', 'nameWithOwner', '-q', '.nameWithOwner'
        ).strip()
    )
    issues = parse(BACKLOG.read_text(encoding='utf-8'))
    if not issues:
        sys.exit(f'no "## NN · Title" sections found in {BACKLOG}')
    print(f'{len(issues)} issues in {BACKLOG.name}; repo {repo}')

    milestones = list(dict.fromkeys(i.milestone for i in issues))
    ensure_milestones(repo, milestones, args.dry_run)
    ensure_labels(
        repo, {label for i in issues for label in i.labels}, args.dry_run
    )

    numbers: dict[str, int | None] = {}
    for issue in issues:
        if issue.key < args.start:
            continue
        title = f'{issue.key} · {issue.title}'
        print(
            f'create issue {title}  [{issue.milestone}; {", ".join(issue.labels)}]'
        )
        if args.dry_run:
            continue
        cmd = [
            'issue',
            'create',
            '--repo',
            repo,
            '--title',
            title,
            '--body',
            body_with_depends(issue, numbers),
            '--milestone',
            issue.milestone,
        ]
        for label in issue.labels:
            cmd += ['--label', label]
        url = gh(*cmd).strip()
        issue.number = int(url.rsplit('/', 1)[-1])
        numbers[issue.key] = issue.number
        print(f'  -> {url}')

    if args.dry_run:
        return 0
    # second pass: resolve forward references
    for issue in issues:
        if issue.number is None:
            continue
        body = body_with_depends(issue, numbers)
        if PLACEHOLDER.search(body):
            print(f'warning: unresolved reference in {issue.key}')
        gh(
            'issue',
            'edit',
            str(issue.number),
            '--repo',
            repo,
            '--body',
            body,
            capture=False,
        )
    print('done')
    return 0


if __name__ == '__main__':
    sys.exit(main())
