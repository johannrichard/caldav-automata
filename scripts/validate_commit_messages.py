#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import subprocess
import sys

ALLOWED_TYPES = (
    "build",
    "ci",
    "chore",
    "docs",
    "feat",
    "fix",
    "perf",
    "refactor",
    "revert",
    "style",
    "test",
)

TYPE_PATTERN = "|".join(ALLOWED_TYPES)
GITMOJI_PATTERN = r":[a-z0-9_-]+:"
SUBJECT_PATTERN = re.compile(
    rf"^(?P<type>{TYPE_PATTERN})(?P<breaking>!)?: "
    rf"(?P<gitmoji>{GITMOJI_PATTERN}) (?P<description>\S.*)$"
)
GITMOJI_REGEX = re.compile(GITMOJI_PATTERN)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate conventional commit subjects with exactly one gitmoji."
    )
    parser.add_argument("commits", nargs="*", help="Commit SHAs to validate")
    parser.add_argument(
        "--range",
        dest="commit_range",
        help="Git revision range to validate, for example origin/main..HEAD",
    )
    args = parser.parse_args()
    if not args.commits and not args.commit_range:
        parser.error("provide commit SHAs or --range")
    return args


def git_output(*command: str) -> str:
    result = subprocess.run(
        ["git", *command],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def load_commit_rows(args: argparse.Namespace) -> list[tuple[str, str, str]]:
    format_string = "%H%x1f%P%x1f%s"
    if args.commit_range:
        output = git_output("log", "--format=" + format_string, args.commit_range)
    else:
        output = git_output(
            "show", "--no-patch", "--format=" + format_string, *args.commits
        )

    if not output:
        return []

    rows: list[tuple[str, str, str]] = []
    for line in output.splitlines():
        commit_sha, parents, subject = line.split("\x1f", 2)
        rows.append((commit_sha, parents, subject))
    return rows


def validation_error(subject: str) -> str | None:
    if not SUBJECT_PATTERN.fullmatch(subject):
        return (
            "expected `type: :gitmoji: description` or `type!: :gitmoji: description` "
            f"with type in {', '.join(ALLOWED_TYPES)}"
        )

    if len(GITMOJI_REGEX.findall(subject)) != 1:
        return "subject must contain exactly one gitmoji token"

    return None


def main() -> int:
    args = parse_args()
    failures: list[tuple[str, str, str]] = []

    for commit_sha, parents, subject in load_commit_rows(args):
        if len(parents.split()) > 1:
            continue

        error = validation_error(subject)
        if error:
            failures.append((commit_sha, subject, error))

    if failures:
        print("Invalid commit message subject(s) detected:", file=sys.stderr)
        for commit_sha, subject, error in failures:
            print(f"- {commit_sha[:7]} {subject}", file=sys.stderr)
            print(f"  {error}", file=sys.stderr)
        return 1

    print("All checked commit messages are valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
