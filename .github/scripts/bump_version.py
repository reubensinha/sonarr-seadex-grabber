#!/usr/bin/env python3
"""Compute the next release tag from existing vX.Y.Z git tags and a bump
type (major/minor/patch, default patch).

If no matching tags exist yet, emits the alpha seed v0.1.0 directly and
skips bump logic entirely - that's the first release.

Reads BUMP_TYPE from the environment (major/minor/patch, default patch).
Prints the new tag and, if GITHUB_OUTPUT is set, appends `new_tag=vX.Y.Z`
to it for later workflow steps to consume.
"""
import os
import re
import subprocess
import sys

TAG_RE = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")


def existing_versions() -> list[tuple[int, int, int]]:
    result = subprocess.run(
        ["git", "tag", "--list", "v*.*.*"], capture_output=True, text=True, check=True
    )
    versions = []
    for line in result.stdout.splitlines():
        match = TAG_RE.match(line.strip())
        if match:
            versions.append(tuple(int(part) for part in match.groups()))
    return versions


def bump(version: tuple[int, int, int], bump_type: str) -> tuple[int, int, int]:
    major, minor, patch = version
    if bump_type == "major":
        return (major + 1, 0, 0)
    if bump_type == "minor":
        return (major, minor + 1, 0)
    return (major, minor, patch + 1)


def main() -> None:
    bump_type = os.environ.get("BUMP_TYPE", "patch").strip().lower()
    if bump_type not in ("major", "minor", "patch"):
        print(f"Unknown BUMP_TYPE {bump_type!r}, defaulting to patch", file=sys.stderr)
        bump_type = "patch"

    versions = existing_versions()
    if not versions:
        new_tag = "v0.1.0"
    else:
        latest = max(versions)
        new_tag = "v{}.{}.{}".format(*bump(latest, bump_type))

    print(new_tag)

    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a", encoding="utf-8") as f:
            f.write(f"new_tag={new_tag}\n")


if __name__ == "__main__":
    main()
