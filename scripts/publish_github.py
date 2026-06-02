#!/usr/bin/env python3
"""
publish_github.py — push a market-lens report to a GitHub repo.

Stdlib-only. Uses git via subprocess. Maintains a clone cache at
~/.cache/market-lens/publish/<owner>__<repo>/.

Usage:
    python3 publish_github.py --repo vishnu-meera/market-lens --report reports/<file>.html
    python3 publish_github.py --repo https://github.com/owner/repo --report <path> \\
        --branch main --subdir docs/reports --yes
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

CACHE_ROOT = Path.home() / ".cache" / "market-lens" / "publish"
INDEX_HEADER = "# Market-Lens Reports\n\nAuto-generated index. Newest first.\n\n"


def run(cmd, cwd=None, check=True):
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        check=check,
    )


def have_git() -> bool:
    return shutil.which("git") is not None


def parse_repo(s: str):
    s = s.strip()
    m = re.match(r"git@github\.com:([\w.-]+)/([\w.-]+?)(?:\.git)?/?$", s)
    if m:
        return m.group(1), m.group(2), s
    m = re.match(r"https?://github\.com/([\w.-]+)/([\w.-]+?)(?:\.git)?/?$", s, re.IGNORECASE)
    if m:
        owner, repo = m.group(1), m.group(2)
        return owner, repo, f"https://github.com/{owner}/{repo}.git"
    m = re.match(r"^([\w.-]+)/([\w.-]+)$", s)
    if m:
        owner, repo = m.group(1), m.group(2)
        return owner, repo, f"https://github.com/{owner}/{repo}.git"
    raise ValueError(
        f"Could not parse GitHub repo from {s!r}. "
        "Expected owner/repo, https://github.com/owner/repo, or git@github.com:owner/repo."
    )


def ensure_clone(push_url: str, owner: str, repo: str, branch: str) -> Path:
    cache_dir = CACHE_ROOT / f"{owner}__{repo}"
    if cache_dir.exists() and (cache_dir / ".git").exists():
        try:
            run(["git", "fetch", "origin"], cwd=cache_dir)
            # Try to check out the requested branch; create from default HEAD if missing
            branches = run(["git", "branch", "-a"], cwd=cache_dir).stdout
            if f"remotes/origin/{branch}" in branches:
                run(["git", "checkout", branch], cwd=cache_dir)
                run(["git", "reset", "--hard", f"origin/{branch}"], cwd=cache_dir)
            else:
                run(["git", "checkout", "-B", branch], cwd=cache_dir)
            run(["git", "clean", "-fd"], cwd=cache_dir)
            return cache_dir
        except subprocess.CalledProcessError:
            shutil.rmtree(cache_dir, ignore_errors=True)

    cache_dir.parent.mkdir(parents=True, exist_ok=True)
    try:
        run(["git", "clone", "--branch", branch, "--single-branch", push_url, str(cache_dir)])
        return cache_dir
    except subprocess.CalledProcessError:
        if cache_dir.exists():
            shutil.rmtree(cache_dir, ignore_errors=True)
        # Fall back to default-branch clone, then create the requested branch locally
        run(["git", "clone", push_url, str(cache_dir)])
        existing = run(["git", "branch", "--list", branch], cwd=cache_dir).stdout.strip()
        if not existing:
            run(["git", "checkout", "-b", branch], cwd=cache_dir)
        else:
            run(["git", "checkout", branch], cwd=cache_dir)
        return cache_dir


def update_index(subdir: Path, filename: str, skill_name: str, timestamp: str, amount) -> None:
    index_path = subdir / "INDEX.md"
    existing = index_path.read_text(encoding="utf-8") if index_path.exists() else INDEX_HEADER
    if not existing.startswith("# Market-Lens"):
        existing = INDEX_HEADER + existing
    amount_str = f"${amount:,.0f}" if isinstance(amount, (int, float)) else "—"
    new_row = f"- [{timestamp} — {skill_name}](./{filename}) — {amount_str}\n"
    parts = existing.split("\n\n", 1)
    if len(parts) == 2:
        new_content = parts[0] + "\n\n" + new_row + parts[1]
    else:
        new_content = existing + "\n" + new_row
    index_path.write_text(new_content, encoding="utf-8")


def report_meta(report_path: Path) -> dict:
    json_path = report_path.with_suffix(".json")
    meta = {"skill_name": report_path.stem, "generated_at": "", "amount": None}
    if json_path.exists():
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
            meta["skill_name"] = data.get("skill_name", meta["skill_name"])
            meta["generated_at"] = data.get("generated_at", "")
            meta["amount"] = data.get("amount")
        except (json.JSONDecodeError, OSError):
            pass
    return meta


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", required=True, help="owner/repo or full GitHub URL")
    ap.add_argument("--report", required=True, help="Path to .html report (sibling .json picked up automatically)")
    ap.add_argument("--branch", default="main")
    ap.add_argument("--subdir", default="reports")
    ap.add_argument("--yes", action="store_true", help="Skip confirmation prompt")
    args = ap.parse_args()

    if not have_git():
        print("git is required but not found on PATH. Install from https://git-scm.com/.", file=sys.stderr)
        return 2

    report_path = Path(args.report).resolve()
    if not report_path.exists():
        print(f"Report not found: {report_path}", file=sys.stderr)
        return 2
    if report_path.suffix.lower() != ".html":
        print(f"Expected an .html report, got {report_path.suffix}", file=sys.stderr)
        return 2
    json_path = report_path.with_suffix(".json")

    try:
        owner, repo, push_url = parse_repo(args.repo)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2

    size_kb = report_path.stat().st_size / 1024
    print(
        f"Will push {report_path.name} ({size_kb:.1f} KB) to "
        f"{owner}/{repo} on branch {args.branch} under {args.subdir}/."
    )
    if not args.yes:
        try:
            resp = input("Continue? [y/N] ").strip().lower()
        except EOFError:
            resp = ""
        if resp not in ("y", "yes"):
            print("Aborted.")
            return 0

    try:
        workdir = ensure_clone(push_url, owner, repo, args.branch)
    except subprocess.CalledProcessError as e:
        print(f"git clone/sync failed:\n{e.stderr or e.stdout}", file=sys.stderr)
        print("If this is an auth issue, try `gh auth setup-git` or add an SSH key for github.com.", file=sys.stderr)
        return 1

    subdir = workdir / args.subdir
    subdir.mkdir(parents=True, exist_ok=True)

    shutil.copy2(report_path, subdir / report_path.name)
    if json_path.exists():
        shutil.copy2(json_path, subdir / json_path.name)

    meta = report_meta(report_path)
    ts = meta["generated_at"] or datetime.now().isoformat(timespec="seconds")
    update_index(subdir, report_path.name, meta["skill_name"], ts, meta["amount"])

    try:
        run(["git", "add", args.subdir], cwd=workdir)
        status = run(["git", "status", "--porcelain"], cwd=workdir).stdout.strip()
        if not status:
            print("Nothing new to commit (file already up-to-date).")
            return 0
        commit_msg = f"Add {meta['skill_name']} report — {ts}"
        run(["git", "commit", "-m", commit_msg], cwd=workdir)
        run(["git", "push", "origin", args.branch], cwd=workdir)
    except subprocess.CalledProcessError as e:
        print(f"git operation failed:\n{e.stderr or e.stdout}", file=sys.stderr)
        print("If this is an auth issue, try `gh auth setup-git` or add an SSH key for github.com.", file=sys.stderr)
        return 1

    blob_url = f"https://github.com/{owner}/{repo}/blob/{args.branch}/{args.subdir}/{report_path.name}"
    print(f"\nPushed: {blob_url}")
    if args.subdir.startswith("docs/"):
        pages_subdir = args.subdir[len("docs/"):].strip("/")
        pages_url = f"https://{owner}.github.io/{repo}/{pages_subdir}/{report_path.name}"
        print(f"  GitHub Pages (if enabled): {pages_url}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
