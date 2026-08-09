"""Report test-script changes from other QA team members.

The QA team pushes to the company remote. This tool finds their commits,
shows which files they touched, and flags files that BOTH sides changed
so nobody silently undoes a teammate's fix. A local review marker
(refs/team-review/last) records how far the review has gotten, so each
run shows only what is new since the last acknowledged review.

Usage:
  python tools/team_changes.py            # fetch + report new team changes
  python tools/team_changes.py --ack      # mark everything reviewed
  python tools/team_changes.py --no-fetch # offline report

Exit codes: 0 = nothing new, 1 = new team changes or divergence to review.
"""
from __future__ import annotations

import argparse
import subprocess
import sys

# Commits by these emails are "ours"; everything else counts as the team.
# Add new self identities here, never remove teammates to silence a report.
SELF_AUTHORS = {
    "justin.varughese@soterixsystems.com",
    "you@example.com",  # pre-2026 local git config
    "noreply@github.com",
}

MARKER_REF = "refs/team-review/last"
COMPANY = "company/main"


def git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args], capture_output=True, text=True, check=False
    )
    if result.returncode != 0 and args[0] not in ("rev-parse", "merge-base"):
        print(f"git {' '.join(args)} failed: {result.stderr.strip()}")
        sys.exit(2)
    return result.stdout.strip()


def marker() -> str | None:
    sha = git("rev-parse", "--quiet", "--verify", MARKER_REF)
    return sha or None


def commits_between(rev_range: str) -> list[dict]:
    out = git("log", rev_range, "--format=%H%x1f%h%x1f%ae%x1f%an%x1f%ad%x1f%s",
              "--date=short")
    commits = []
    for line in out.splitlines():
        full, short, email, name, date, subject = line.split("\x1f")
        commits.append({
            "sha": full, "short": short, "email": email,
            "name": name, "date": date, "subject": subject,
        })
    return commits


def files_of(sha: str) -> list[str]:
    out = git("show", sha, "--name-only", "--format=")
    return [f for f in out.splitlines() if f]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ack", action="store_true",
                        help="mark current state as reviewed")
    parser.add_argument("--no-fetch", action="store_true",
                        help="skip git fetch (offline)")
    args = parser.parse_args()

    if not args.no_fetch:
        print("Fetching remotes...")
        subprocess.run(["git", "fetch", "company"], check=False)
        subprocess.run(["git", "fetch", "origin"], check=False)

    findings = 0

    # 1. Divergence: company commits we do not have. This is where silent
    #    merge losses start (see memory: losses hide OUTSIDE conflicts).
    unmerged = commits_between(f"main..{COMPANY}")
    if unmerged:
        findings += 1
        print(f"\n[DIVERGENCE] {len(unmerged)} commit(s) on {COMPANY} not in main:")
        for c in unmerged:
            print(f"  {c['short']} {c['date']} {c['name']}: {c['subject']}")
        print("  Merge carefully: check files git merges WITHOUT conflict for")
        print("  size drops - past losses happened in unopposed files.")

    # 2. Team commits in main since the last review marker.
    m = marker()
    rev_range = f"{m}..main" if m else "main"
    team = [c for c in commits_between(rev_range) if c["email"] not in SELF_AUTHORS]

    if team:
        findings += 1
        print(f"\n[TEAM CHANGES] {len(team)} unreviewed team commit(s) in main:")
        team_files: set[str] = set()
        for c in team:
            print(f"\n  {c['short']} {c['date']} {c['name']} <{c['email']}>")
            print(f"    {c['subject']}")
            for f in files_of(c["sha"]):
                team_files.add(f)
                print(f"      {f}")

        # 3. Overlap: team-touched files that we also changed since the
        #    marker. These need a "did their fix survive?" look.
        ours = [c for c in commits_between(rev_range) if c["email"] in SELF_AUTHORS]
        our_files: set[str] = set()
        for c in ours:
            our_files.update(files_of(c["sha"]))
        overlap = sorted(team_files & our_files)
        if overlap:
            print(f"\n[OVERLAP - VERIFY THEIR FIXES SURVIVED] {len(overlap)} file(s)")
            print("  changed by both sides since the last review:")
            for f in overlap:
                print(f"    {f}")
            print("  For each file: git log -p <their-sha> -- <file>, then check")
            print("  the same logic in HEAD. Study their approach; adopt or")
            print("  improve it, do not silently replace it.")
    elif not unmerged:
        print("\nNo new team changes since the last review.")

    if args.ack:
        head = git("rev-parse", "main")
        git("update-ref", MARKER_REF, head)
        print(f"\nReview marker set to {head[:9]}.")

    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
