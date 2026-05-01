#!/usr/bin/env python3
"""
EAR Release Automation Script
Usage: python release.py <version> [message]
Example: python release.py 0.11.0 "Add LiteLLM execution runtime"
"""

import re
import subprocess
import sys
from pathlib import Path

PYPROJECT = Path(__file__).parent / "pyproject.toml"
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")


def run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    print(f"  > {' '.join(cmd)}")
    return subprocess.run(cmd, check=check, capture_output=True, text=True)


def fail(msg: str) -> None:
    print(f"\nERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def validate_version(version: str) -> None:
    if not VERSION_RE.match(version):
        fail(f"Version '{version}' must be in MAJOR.MINOR.PATCH format (e.g. 0.11.0)")


def check_clean_tree() -> None:
    result = run(["git", "status", "--porcelain"])
    if result.stdout.strip():
        fail("Working tree is not clean. Commit or stash changes before releasing.\n" + result.stdout)


def check_tag_not_exists(version: str) -> None:
    result = run(["git", "tag", "--list", version])
    if result.stdout.strip():
        fail(f"Tag '{version}' already exists locally. Choose a different version.")


def bump_version(version: str) -> None:
    content = PYPROJECT.read_text(encoding="utf-8")
    new_content = re.sub(r'^version\s*=\s*"[^"]+"', f'version = "{version}"', content, flags=re.MULTILINE)
    if new_content == content:
        fail("Could not find version field in pyproject.toml")
    PYPROJECT.write_text(new_content, encoding="utf-8")
    print(f"  Bumped pyproject.toml → {version}")


def commit_and_push(version: str, message: str) -> None:
    run(["git", "add", "pyproject.toml"])
    run(["git", "commit", "-m", f"chore(release): bump version to {version} — {message}"])
    run(["git", "push", "origin", "master"])
    run(["git", "push", "origin", "master:main"])


def create_and_push_tag(version: str, message: str) -> None:
    run(["git", "tag", "-a", version, "-m", f"{version}: {message}"])
    run(["git", "push", "origin", f"refs/tags/{version}"])


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    version = sys.argv[1].lstrip("v")  # strip leading 'v' if provided
    message = sys.argv[2] if len(sys.argv) > 2 else f"Release {version}"

    print(f"\nEAR Release: {version}")
    print(f"Message    : {message}\n")

    print("[1/5] Validating version format...")
    validate_version(version)

    print("[2/5] Checking working tree is clean...")
    check_clean_tree()

    print("[3/5] Verifying tag does not already exist...")
    check_tag_not_exists(version)

    print("[4/5] Bumping version in pyproject.toml...")
    bump_version(version)

    print("[5/5] Committing, pushing master+main, tagging, and pushing tag...")
    commit_and_push(version, message)
    create_and_push_tag(version, message)

    print(f"\nRelease {version} complete.")
    print(f"  GitHub Actions will now build and publish to PyPI if CI passes.")


if __name__ == "__main__":
    main()
