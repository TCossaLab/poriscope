#!/usr/bin/env python3
"""Check a skill's shape, or a whole skills root's layout, before trusting that it loads.

Why this exists: a skill can be well written and still never reach a session. Claude Code
discovers only ``<root>/<name>/SKILL.md``, so a folder nested one level too deep loads
nothing; a stale synced copy of the same skill can load instead of the one being edited;
a description over 1,024 characters works locally but fails a claude.ai upload; and a
lesson heading missing from the index cannot be found by grep. None of these fails
loudly. This script checks for each.

Skill mode (one skill folder):
  - frontmatter starts on line 1, parses, and has a description;
  - name matches the folder and the spec (lowercase, digits, single hyphens, <= 64);
  - description <= 1,536 (Claude Code cap, error) and <= 1,024 (upload limit, warning);
  - frontmatter keys the upload spec rejects, or that Claude Code ignores (warnings);
  - SKILL.md <= 500 lines and <= 20,000 characters (about 5,000 tokens, the part
    compaction keeps);
  - reference files over 300 lines have a Contents section;
  - every relative link outside templates/ resolves (with --root, a nested skill's
    links into its siblings break too);
  - every lesson heading (``## X1 · title``, or ``###`` under a grouping heading) is in reference/lesson-index.md, every index
    entry has a heading here or in a --siblings skill, and no ID is used twice.

Root mode (--root, default ~/.claude/skills):
  - SKILL.md files nested deeper than <root>/<name>/SKILL.md (never discovered);
  - top-level folders with no SKILL.md, and reserved folder names;
  - personal skills that also exist as a claude.ai synced copy, with how many files differ.

Usage:
    python check_skill.py ~/.claude/skills/building-skills
    python check_skill.py ~/.claude/skills/refactoring-codebases/refactoring-codebases \\
        --siblings ~/.claude/skills/planning-and-executing-changes
    python check_skill.py --root
    python check_skill.py --root path/to/repo/.claude/skills

Exit status is 1 if any ERROR was reported, otherwise 0.
"""
from __future__ import annotations

import argparse
import filecmp
import re
import sys
from pathlib import Path

SPEC_KEYS = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
CLAUDE_CODE_KEYS = SPEC_KEYS | {
    "when_to_use", "argument-hint", "arguments", "disable-model-invocation", "user-invocable",
    "disallowed-tools", "model", "effort", "context", "agent", "background", "hooks", "paths",
    "shell",
}
NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
HEADING_ID_RE = re.compile(r"^#{2,3} ([A-Z]+\d+) ·", re.M)
INDEX_ID_RE = re.compile(r"^- \*\*([A-Z]+\d+)\*\*", re.M)
IGNORED_TOP_LEVEL = {".trash", "synced"}

DESC_HARD_CAP = 1536
DESC_UPLOAD_CAP = 1024
MAX_LINES = 500
MAX_CHARS = 20_000
CONTENTS_THRESHOLD = 300


class Report:
    def __init__(self) -> None:
        self.errors = 0

    def error(self, msg: str) -> None:
        self.errors += 1
        print(f"ERROR {msg}")

    def warn(self, msg: str) -> None:
        print(f"WARN  {msg}")

    def ok(self, msg: str) -> None:
        print(f"OK    {msg}")


def parse_frontmatter(text: str) -> dict[str, str] | None:
    """Return top-level frontmatter keys and their values, or None if there is no block.

    Deliberately minimal (no YAML dependency): ``key: value`` lines, with indented or
    block-scalar continuation lines folded into the previous key.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    fields: dict[str, str] = {}
    key = None
    for line in lines[1:]:
        if line.strip() == "---":
            return {k: v.strip().strip("'\"") for k, v in fields.items()}
        match = re.match(r"^([A-Za-z_][\w-]*):\s?(.*)$", line)
        if match:
            key = match.group(1)
            value = match.group(2)
            fields[key] = "" if value in (">", "|", ">-", "|-") else value
        elif key is not None and line.startswith((" ", "\t")):
            fields[key] = (fields[key] + " " + line.strip()).strip()
    return None


def strip_code_fences(text: str) -> str:
    return re.sub(r"^```.*?^```", "", text, flags=re.S | re.M)


def lesson_heading_ids(skill: Path) -> list[str]:
    ids: list[str] = []
    ref = skill / "reference"
    if ref.is_dir():
        for md in sorted(ref.glob("*.md")):
            if md.name != "lesson-index.md":
                ids += HEADING_ID_RE.findall(md.read_text(encoding="utf-8"))
    return ids


def check_skill(skill: Path, siblings: list[Path], rep: Report) -> None:
    skill_md = skill / "SKILL.md"
    if not skill_md.is_file():
        rep.error(f"{skill}: no SKILL.md")
        return
    text = skill_md.read_text(encoding="utf-8")
    fm = parse_frontmatter(text)
    if fm is None:
        rep.error("SKILL.md: frontmatter missing, not on line 1, or unterminated - the skill loads with no description")
        fm = {}

    name = fm.get("name", skill.name)
    if name != skill.name:
        rep.error(f"name '{name}' does not match folder '{skill.name}'")
    if len(name) > 64 or not NAME_RE.match(name):
        rep.error(f"name '{name}' breaks the spec (lowercase letters, digits, single hyphens, <= 64)")

    desc = fm.get("description", "")
    if not desc:
        rep.error("no description - nothing for the model to match a request against")
    elif len(desc) > DESC_HARD_CAP:
        rep.error(f"description is {len(desc)} chars; Claude Code truncates at {DESC_HARD_CAP}")
    elif len(desc) > DESC_UPLOAD_CAP:
        rep.warn(f"description is {len(desc)} chars; a claude.ai/API upload rejects over {DESC_UPLOAD_CAP}")
    else:
        rep.ok(f"description {len(desc)} chars")

    for key in fm:
        if key not in CLAUDE_CODE_KEYS:
            rep.warn(f"frontmatter key '{key}' is unknown to Claude Code and silently ignored")
        elif key not in SPEC_KEYS:
            rep.warn(f"frontmatter key '{key}' works in Claude Code but fails a claude.ai/API upload")

    n_lines, n_chars = len(text.splitlines()), len(text)
    if n_lines > MAX_LINES or n_chars > MAX_CHARS:
        rep.warn(f"SKILL.md is {n_lines} lines / {n_chars} chars (limits {MAX_LINES} / {MAX_CHARS}); "
                 "compaction keeps only the first ~5,000 tokens")
    else:
        rep.ok(f"SKILL.md {n_lines} lines / {n_chars} chars (~{n_chars // 4} tokens)")

    broken = 0
    for md in sorted(skill.rglob("*.md")):
        if "templates" in md.relative_to(skill).parts:
            continue  # skeletons link to the files a new skill will have, not to this one's
        body = strip_code_fences(md.read_text(encoding="utf-8"))
        for target in LINK_RE.findall(body):
            if re.match(r"^[a-z]+:", target) or target.startswith("#") or "<" in target:
                continue
            path = target.split("#", 1)[0]
            if path and not (md.parent / path).exists():
                broken += 1
                rep.error(f"{md.relative_to(skill)}: link to '{target}' does not resolve")
    if not broken:
        rep.ok("all relative links resolve")

    ref = skill / "reference"
    if ref.is_dir():
        for md in sorted(ref.glob("*.md")):
            md_text = md.read_text(encoding="utf-8")
            if len(md_text.splitlines()) > CONTENTS_THRESHOLD and "## Contents" not in md_text:
                rep.warn(f"{md.relative_to(skill)} is over {CONTENTS_THRESHOLD} lines with no '## Contents'")

    own = lesson_heading_ids(skill)
    index_file = ref / "lesson-index.md"
    if not own and not index_file.is_file():
        return
    sibling_ids: list[str] = []
    for sib in siblings:
        sibling_ids += lesson_heading_ids(sib)
    seen: set[str] = set()
    for lid in own + sibling_ids:
        if lid in seen:
            rep.error(f"lesson ID {lid} is used more than once across this skill and its siblings")
        seen.add(lid)
    if not index_file.is_file():
        rep.error("lessons exist but reference/lesson-index.md does not")
        return
    indexed = set(INDEX_ID_RE.findall(index_file.read_text(encoding="utf-8")))
    missing = [lid for lid in own if lid not in indexed]
    orphans = sorted(indexed - seen)
    for lid in missing:
        rep.error(f"lesson {lid} has a heading but no lesson-index entry")
    for lid in orphans:
        hint = "" if siblings else " (if it lives in a sibling skill, pass --siblings)"
        rep.error(f"lesson-index lists {lid} but no reference file has its heading{hint}")
    if not missing and not orphans:
        rep.ok(f"{len(own)} lesson headings and the index agree")


def differing_files(a: Path, b: Path) -> int:
    def walk(cmp: filecmp.dircmp) -> int:
        n = len(cmp.left_only) + len(cmp.right_only) + len(cmp.diff_files) + len(cmp.funny_files)
        return n + sum(walk(sub) for sub in cmp.subdirs.values())

    return walk(filecmp.dircmp(a, b))


def check_root(root: Path, rep: Report) -> None:
    if not root.is_dir():
        rep.error(f"{root} is not a directory")
        return
    personal: dict[str, Path] = {}
    for child in sorted(p for p in root.iterdir() if p.is_dir()):
        if child.name in IGNORED_TOP_LEVEL:
            continue
        if child.name.startswith("anthropic-skills"):
            rep.error(f"{child.name}: names starting 'anthropic-skills' do not load outside a plugin")
        if (child / "SKILL.md").is_file():
            personal[child.name] = child
            rep.ok(f"{child.name}")
            continue
        nested = sorted(child.rglob("SKILL.md"))
        if nested:
            for found in nested:
                rel = found.relative_to(root)
                rep.error(f"{rel}: nested too deep - only <root>/<name>/SKILL.md is discovered, "
                          f"so this skill never loads")
                personal.setdefault(found.parent.name, found.parent)
        else:
            rep.warn(f"{child.name}: folder has no SKILL.md")

    synced_root = root / "synced"
    if synced_root.is_dir():
        for synced_md in sorted(synced_root.glob("*/*/SKILL.md")):
            name = synced_md.parent.name
            if name not in personal:
                continue
            n = differing_files(personal[name], synced_md.parent)
            if n:
                rep.warn(f"{name}: a claude.ai synced copy also loads (as anthropic-skills:{name}) and "
                         f"differs from {personal[name].relative_to(root)} in {n} file(s) - "
                         f"re-upload the source or remove the stale copy")
            else:
                rep.ok(f"{name}: synced copy is identical")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("skill", nargs="?", type=Path, help="a skill folder (the one holding SKILL.md)")
    parser.add_argument("--root", nargs="?", const=Path.home() / ".claude" / "skills", type=Path,
                        help="check a skills root's layout instead (default ~/.claude/skills)")
    parser.add_argument("--siblings", nargs="*", type=Path, default=[],
                        help="skills sharing this one's lesson-ID space, for the index and uniqueness checks")
    args = parser.parse_args()
    if args.root is None and args.skill is None:
        parser.error("give a skill folder, or --root")

    rep = Report()
    if args.root is not None:
        print(f"== root {args.root}")
        check_root(args.root.expanduser(), rep)
    if args.skill is not None:
        print(f"== skill {args.skill}")
        check_skill(args.skill.expanduser(), [s.expanduser() for s in args.siblings], rep)
    return 1 if rep.errors else 0


if __name__ == "__main__":
    sys.exit(main())
