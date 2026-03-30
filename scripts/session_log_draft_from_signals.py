#!/usr/bin/env python3
"""
Build a session log entry stub from Cursor hook signals (docs/session_logs/.tracking/signals.jsonl).

Hooks only append path/topic lines; they do not commit finished session prose. Run this when
closing a scoped task so the agent (or human) can paste/edit the body and append MANIFEST.md.

Usage:
  python scripts/session_log_draft_from_signals.py --print
  python scripts/session_log_draft_from_signals.py --write --slug my-feature [--date 2026-03-24]
"""
from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_signals(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    rows: list[dict] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def _dedupe_paths(rows: list[dict]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for r in rows:
        p = r.get("path")
        if isinstance(p, str) and p and p not in seen:
            seen.add(p)
            out.append(p)
    return sorted(out)


def _topic_union(rows: list[dict]) -> list[str]:
    bag: dict[str, None] = {}
    for r in rows:
        topics = r.get("topics", [])
        if isinstance(topics, list):
            for t in topics:
                if isinstance(t, str) and t:
                    bag[t] = None
    return sorted(bag.keys())


def _build_markdown(*, session_slug: str, day: date, paths: list[str], topics: list[str]) -> str:
    ym = day.isoformat()
    topics_yaml = "[" + ", ".join(topics) + "]" if topics else "[]"
    lines = [
        "---",
        f"session_slug: {session_slug}",
        f"date: {ym}",
        "depends_on: []",
        "follow_up: []",
        f"topics: {topics_yaml}",
        "touched_paths:",
    ]
    for p in paths:
        lines.append(f"  - {p}")
    lines.extend(
        [
            "related_commits: []",
            "planning_refs: []",
            "supersedes_session: null",
            "---",
            "",
            "## Context",
            "",
            "- Goal:",
            "- Constraints:",
            "",
            "## Changes",
            "",
            "- (Summarize by area; hook only listed paths.)",
            "",
            "## Decisions",
            "",
            "- (Or: see docs/planning/SUMMARY.md)",
            "",
            "## Verification",
            "",
            "- Tests:",
            "- Manual:",
            "",
            "## Links",
            "",
            "-",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Draft session log from .tracking/signals.jsonl")
    parser.add_argument("--write", action="store_true", help="Write entries/YYYY-MM-DD_<slug>.md")
    parser.add_argument("--slug", type=str, default="", help="session_slug and file slug (required for --write)")
    parser.add_argument("--date", type=str, default="", help="YYYY-MM-DD (default: today)")
    parser.add_argument(
        "--no-clear",
        action="store_true",
        help="With --write, keep signals.jsonl instead of truncating",
    )
    args = parser.parse_args()

    root = _repo_root()
    signals_path = root / "docs" / "session_logs" / ".tracking" / "signals.jsonl"
    rows = _load_signals(signals_path)
    if not rows:
        print("No signals in docs/session_logs/.tracking/signals.jsonl (edit tracked files in Cursor first).")
        return 0

    paths = _dedupe_paths(rows)
    topics = _topic_union(rows)

    day = date.today()
    if args.date:
        day = date.fromisoformat(args.date)

    if not args.write:
        session_slug = args.slug or "replace-me"
        text = _build_markdown(session_slug=session_slug, day=day, paths=paths, topics=topics)
        print(text)
        return 0

    if not args.slug:
        print("--slug is required with --write", file=__import__("sys").stderr)
        return 2

    session_slug = args.slug
    filename = f"{day.isoformat()}_{session_slug}.md"
    out_path = root / "docs" / "session_logs" / "entries" / filename
    text = _build_markdown(session_slug=session_slug, day=day, paths=paths, topics=topics)
    out_path.write_text(text, encoding="utf-8")
    print(f"Wrote {out_path.relative_to(root)}")
    print("Append a row to docs/session_logs/MANIFEST.md (newest first).")
    if not args.no_clear and signals_path.is_file():
        signals_path.write_text("", encoding="utf-8")
        print("Cleared signals file.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
