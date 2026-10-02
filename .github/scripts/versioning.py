"""Version checks and release-note extraction for the Logbook app.

Standard library only. Run from anywhere inside the repository.

    versioning.py version        print the version from logbook/config.yaml
    versioning.py check          validate version, changelog and tags (exit 1 on a problem)
    versioning.py notes VERSION  print the changelog section for VERSION

Policy: docs/versioning.md
"""
import os
import re
import subprocess
import sys

ROOT = subprocess.run(['git', 'rev-parse', '--show-toplevel'], capture_output=True, text=True,
                      check=True).stdout.strip()
CONFIG = os.path.join(ROOT, 'logbook', 'config.yaml')
CHANGELOG = os.path.join(ROOT, 'logbook', 'CHANGELOG.md')
SEMVER = re.compile(r'^(\d+)\.(\d+)\.(\d+)$')


def parse(v):
    m = SEMVER.match(v)
    return tuple(int(x) for x in m.groups()) if m else None


def read_version():
    for line in open(CONFIG, encoding='utf-8'):
        m = re.match(r'''^version:\s*["']?([^"'\s#]+)["']?\s*(?:#.*)?$''', line)
        if m:
            return m.group(1)
    raise SystemExit('ERROR: no "version:" line found in logbook/config.yaml')


def changelog_versions():
    text = open(CHANGELOG, encoding='utf-8').read()
    return re.findall(r'^## (\d+\.\d+\.\d+)(?=\s|$)', text, re.M)


def git(*args):
    return subprocess.run(['git', '-C', ROOT, *args], capture_output=True, text=True, check=True).stdout.strip()


def release_tags():
    tags = {}
    for t in git('tag', '--list', 'v*').splitlines():
        v = parse(t[1:])
        if v:
            tags[t[1:]] = git('rev-list', '-n', '1', t)
    return tags


def check():
    version = read_version()
    problems = []

    if not parse(version):
        problems.append(f'version "{version}" in logbook/config.yaml is not MAJOR.MINOR.PATCH (for example 1.2.3)')

    entries = changelog_versions()
    if not entries:
        problems.append('logbook/CHANGELOG.md has no "## X.Y.Z" headings')
    elif entries[0] != version:
        problems.append(f'the first changelog entry is "{entries[0]}" but config.yaml says "{version}". '
                        f'Add a "## {version}" section at the top of logbook/CHANGELOG.md')

    if parse(version):
        tags = release_tags()
        head = os.environ.get('GITHUB_SHA') or git('rev-parse', 'HEAD')
        is_pr = os.environ.get('GITHUB_EVENT_NAME') == 'pull_request'
        if version in tags:
            if is_pr or tags[version] != head:
                problems.append(f'version {version} is already released as tag v{version} on a different commit. '
                                f'Bump the version in logbook/config.yaml and add a changelog entry')
        elif tags:
            highest = max(tags, key=parse)
            if parse(version) <= parse(highest):
                problems.append(f'version {version} is not newer than the latest released version {highest}')

    if problems:
        print('Version check FAILED:')
        for p in problems:
            print(f'  - {p}')
        return 1
    state = 'already released at this commit' if parse(version) and version in release_tags() else 'new, will be released'
    print(f'Version check OK: {version} ({state})')
    return 0


def notes(version):
    lines = open(CHANGELOG, encoding='utf-8').read().splitlines()
    out, inside = [], False
    for line in lines:
        if re.match(r'^## ', line):
            if inside:
                break
            inside = re.match(rf'^## {re.escape(version)}(?=\s|$)', line) is not None
            continue
        if inside:
            out.append(line)
    text = '\n'.join(out).strip()
    if not text:
        raise SystemExit(f'ERROR: no changelog section found for {version}')
    print(text)


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else ''
    if cmd == 'version':
        print(read_version())
    elif cmd == 'check':
        sys.exit(check())
    elif cmd == 'notes' and len(sys.argv) == 3:
        notes(sys.argv[2])
    else:
        print(__doc__)
        sys.exit(2)
