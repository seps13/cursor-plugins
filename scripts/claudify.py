#!/usr/bin/env python3
"""Rewrite the selected pstack skills for Claude Code.

Replaces Cursor-isms (Task tool, generalPurpose, readonly, cloud workers,
~/.cursor paths, grok/xhigh model slugs) with Claude Code equivalents, and
points model lookup at ~/.claude/rules/pstack-models.md, written by the
Claude Code setup-pstack in claude-code/setup-pstack/.

Upstream's pstack/docs/harness/claude-code.md is the spec for each mapping,
and TERMS mirrors upstream's scripts/generate-pstack-harness-trees.mjs. A new
upstream term lands there first, so a missed rewrite fails the leftover scan.

Every replacement asserts its expected match count, so an upstream wording
change fails loudly instead of silently leaving a Cursor-ism behind.

Upstream bump: rebase seps13-patches onto the new upstream, drop the old
"Apply claudify.py" commit, run this script, commit the result.

Usage: python3 scripts/claudify.py [--check]
"""

import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / "pstack" / "skills"

CONFIG = "`~/.claude/rules/pstack-models.md`"
LOADED = "Claude Code loads that file into every session, so read it only if its lines are not in context."
VALUE_FORMAT = "A value is `<model>/<effort>`, e.g. `sonnet/high`: pass them as the Agent tool's `model` and `effort`."
TRANSCRIPT_DIR = (
    "`~/.claude/projects/<slug>/`, where `<slug>` is the absolute working directory "
    "with every non-alphanumeric character replaced by `-`"
)

OLD_ROLE_RULE_TAIL = (
    "a role line in the `pstack-models.mdc` rule and a default. Set `model` to that line's "
    "value, or to the default if the rule or the line is missing. Leave `model` unset when "
    "the value is `auto` or `inherit-parent`. If the Task tool rejects a slug, use the default "
    "and say so. If it rejects the default, use the closest valid slug of the same family "
    "from its error message."
)
NEW_ROLE_RULE_TAIL = (
    f"a role line in {CONFIG} and a default. {LOADED} {VALUE_FORMAT} Use the default if the "
    "file or the line is missing. Leave both unset when the value is `inherit`."
)

# poteto-mode isn't selected; this inlines what its Subagents section says.
OLD_EFFORT = (
    " Pick each subagent's reasoning level and fast or standard speed for the job, per the "
    "Subagents section of the **poteto-mode** skill."
)
NEW_EFFORT = " Raise or lower a subagent's `effort` to fit the job, but keep its `model`."
EFFORT_USERS = (
    "arena",
    "interrogate",
    "why",
    "how",
    "reflect",
    "swarm",
    "show-me-your-work",
    "no-comments",
    "recall",
)

OLD_ROUTING = (
    "(under `.cursor/skills/`, `~/.cursor/skills/`, or `~/.cursor/plugins/`), a `Task` prompt "
    "naming its path, or a tool call (Shell, Grep, MCP, etc.)"
)
NEW_ROUTING = (
    "(under `.claude/skills/`, `~/.claude/skills/`, or `~/.claude/plugins/`), an Agent prompt "
    "naming its path, or a tool call (Bash, Grep, MCP, etc.)"
)

# Called by other skills (blast-radius, no-comments, architect, teach, recall, dev-workflow:prototype),
# wanted on demand (tdd), or loaded by a user rule (typescript-best-practices, via rules/typescript.md).
MODEL_INVOKED = (
    "how",
    "why",
    "unslop",
    "architect",
    "arena",
    "benchmark-checklist",
    "tdd",
    "typescript-best-practices",
)

# (path relative to pstack/skills, old, new, expected count). Literal unless old is re.Pattern.
EDITS: list[tuple[str, str | re.Pattern[str], str, int]] = [
    *[(f"{name}/SKILL.md", OLD_EFFORT, NEW_EFFORT, 1) for name in EFFORT_USERS],
    *[(f"{name}/SKILL.md", "Open a todolist", "Open a TodoWrite list", 1) for name in ("architect", "arena", "swarm")],
    # how
    (
        "how/SKILL.md",
        "Every spawn is a Task subagent with `subagent_type: generalPurpose` and `readonly: true`. "
        "Explorers use the `how explorer` line in the `pstack-models.mdc` rule (default "
        "`grok-4.7-xhigh-fast`), and every explainer uses the `how explainer` line (default "
        "`claude-opus-5-5-xhigh`). Set `model` to that line's value, or to the default if the rule "
        "or the line is missing. Leave `model` unset when the value is `auto` or `inherit-parent`. "
        "If the Task tool rejects a slug, use the default and say so. If it rejects the default, "
        "use the closest valid slug of the same family from its error message.",
        'Every explorer is an Agent subagent with `subagent_type: "Explore"` and the `how '
        f"explorer` line in {CONFIG} (default `haiku/high`). Every explainer is a "
        "`general-purpose` subagent told not to modify files, with the `how explainer` line "
        f"(default `opus/medium`). {LOADED} {VALUE_FORMAT} Use the default if the file or the "
        "line is missing. Leave both unset when the value is `inherit`.",
        1,
    ),
    # why
    ("why/SKILL.md", OLD_ROLE_RULE_TAIL, NEW_ROLE_RULE_TAIL, 1),
    (
        "why/SKILL.md",
        "Every spawn is `generalPurpose` with `readonly: false` (agent mode). **Do not use "
        "readonly/Ask mode.** It strips MCP access, which disables the MCP-backed investigators "
        "and the synthesizer's citation spot-checks. Investigators still shouldn't write anything.",
        'Every spawn is `subagent_type: "general-purpose"`, which keeps the session\'s MCP '
        "servers that the MCP-backed investigators and the synthesizer's citation spot-checks "
        "need. Do not use `Explore`. Investigators still shouldn't write anything, so say so in "
        "the brief.",
        1,
    ),
    (
        "why/SKILL.md",
        "list the available MCPs from the Cursor environment. Use the available-tools map when "
        "present. Otherwise inspect the `mcps/` directory Cursor exposes for enabled MCP servers.",
        "list the MCP tools available in this session: tool names starting with `mcp__`, "
        "including deferred tools named in system reminders.",
        1,
    ),
    (
        "why/SKILL.md",
        "`why investigators` line, default `grok-4.7-xhigh-fast`",
        "`why investigators` line, default `haiku/high`",
        1,
    ),
    (
        "why/SKILL.md",
        "`why synthesizer` line, default `claude-opus-5-5-xhigh`",
        "`why synthesizer` line, default `opus/medium`",
        1,
    ),
    # reflect
    ("reflect/SKILL.md", OLD_ROLE_RULE_TAIL, NEW_ROLE_RULE_TAIL, 1),
    (
        "reflect/SKILL.md",
        "find this conversation's transcript in the `agent-transcripts/` directory the system "
        "prompt names. Do not glob across `~/.cursor/projects/*/`.",
        f"find this conversation's transcript in {TRANSCRIPT_DIR}. Call that directory "
        "`<transcripts>`. Do not glob across `~/.claude/projects/*/`.",
        1,
    ),
    (
        "reflect/SKILL.md",
        "ls -t <agent-transcripts>/*.jsonl <agent-transcripts>/*/*.jsonl <agent-transcripts>/*/subagents/*.jsonl",
        "ls -t <transcripts>/*.jsonl <transcripts>/*/subagents/*.jsonl",
        1,
    ),
    (
        "reflect/SKILL.md",
        "That covers the legacy flat (`<id>.jsonl`), current nested (`<id>/<id>.jsonl`), and "
        "subagent (`<parent>/subagents/<child>.jsonl`) layouts. For each candidate, read the first "
        "JSONL line. Take the file whose `message.content[0].text` contains",
        "That covers the session (`<id>.jsonl`) and subagent (`<id>/subagents/<child>.jsonl`) "
        'layouts. For each candidate, find the first line with `"type": "user"`. Take the file '
        "whose `message.content` contains",
        1,
    ),
    (
        "reflect/SKILL.md",
        "One message, three `Task` calls, `subagent_type: generalPurpose`, agent mode (`readonly: "
        "false`). Reviewers need MCP access to look up the tickets, chat threads, and observability "
        "traces the transcript references, and readonly strips MCPs.",
        'One message, three Agent calls, `subagent_type: "general-purpose"`. Reviewers need MCP '
        "access to look up the tickets, chat threads, and observability traces the transcript "
        "references, which `general-purpose` keeps.",
        1,
    ),
    ("reflect/SKILL.md", "in the `Task` response body", "in the Agent result", 1),
    (
        "reflect/SKILL.md",
        "One `Task` call, `subagent_type: generalPurpose`, `model` from the",
        'One Agent call, `subagent_type: "general-purpose"`, `model` and `effort` from the',
        1,
    ),
    (
        "reflect/SKILL.md",
        ", agent mode (`readonly: false`). It spot-verifies citations through MCP, and readonly strips MCPs.",
        ". It spot-verifies citations through MCP, which `general-purpose` keeps.",
        1,
    ),
    ("reflect/SKILL.md", "`claude-opus-5-5-xhigh`", "`opus/medium`", 3),
    ("reflect/SKILL.md", "`grok-4.7-xhigh-fast`", "`sonnet/medium`", 1),
    (
        "reflect/SKILL.md",
        "hand to Cursor's built-in `create-skill` skill and run",
        "hand to the `skill-creator` skill (edit directly if it isn't installed) and run",
        1,
    ),
    ("reflect/SKILL.md", re.compile(r"\bcreate-skill\b"), "skill-creator", 3),
    ("reflect/references/synthesizer.md", re.compile(r"\bcreate-skill\b"), "skill-creator", 3),
    *[
        (f"reflect/references/{name}.md", OLD_ROUTING, NEW_ROUTING, 1)
        for name in ("judgment-reviewer", "tooling-reviewer", "divergent-reviewer")
    ],
    # show-me-your-work
    (
        "show-me-your-work/SKILL.md",
        "Read this run's transcript under the active workspace's `agent-transcripts/` directory "
        "(the system prompt names the path). Don't glob across `~/.cursor/projects/*/`.",
        f"Read this run's transcript: the newest `*.jsonl` under {TRANSCRIPT_DIR}. Don't glob "
        "across `~/.claude/projects/*/`.",
        1,
    ),
    # recall
    (
        "recall/SKILL.md",
        "Transcripts live at `~/.cursor/projects/<slug>/agent-transcripts/<uuid>/<uuid>.jsonl`, "
        'where `<slug>` is the workspace path with the leading slash dropped and each "/" turned '
        'into "-" (so `/Users/you/proj` becomes `Users-you-proj`).',
        f"Transcripts live at `<uuid>.jsonl` under {TRANSCRIPT_DIR}. Subagent transcripts sit "
        "under `<uuid>/subagents/`.",
        1,
    ),
    (
        "recall/SKILL.md",
        "One specific prior chat to resume is the `session-pickup` playbook, not this. Turning "
        "habits into a durable skill is `automate-me`.",
        "Resuming one specific prior chat is `claude --resume`, not this.",
        1,
    ),
    # arena
    (
        "arena/SKILL.md",
        "Use the `arena runners` line in `~/.cursor/rules/pstack-models.mdc`. If the rule or that "
        "line is missing, default to one each on `claude-opus-5-5-xhigh` and `grok-4.7-xhigh-fast`. "
        "An `auto` or `inherit-parent` entry in this line or the cross-judge line means the parent "
        "model, so omit `model` for it. If the Task tool rejects a configured entry, run that seat "
        "on its family's default and say so. Families go by prefix: `claude-*`, and `grok-*` with "
        "`cursor-grok-*` and `composer-*`. A refused `composer-*` entry runs on "
        "`grok-4.7-xhigh-fast`. With no family match, use `claude-opus-5-5-xhigh`. If it rejects a "
        "default, use the closest valid slug of the same family from its error message.",
        f"Use the `arena runners` line in {CONFIG}. {LOADED} If the file or that line is missing, "
        f"default to one each on `opus/medium` and `sonnet/high`. {VALUE_FORMAT} An `inherit` "
        "entry in this line or the cross-judge line means the parent model, so omit both for it.",
        1,
    ),
    ("arena/SKILL.md", "in one message with `run_in_background: true`, each with", "in one message, each with", 1),
    (
        "arena/SKILL.md",
        "line in `~/.cursor/rules/pstack-models.mdc`. If the rule or that line is missing, choose "
        "from `claude-opus-5-5-xhigh` and `grok-4.7-xhigh-fast`. Prefer a different model family "
        "from the parent's. Spawn one readonly judge subagent on that model.",
        f"line in {CONFIG}. If the file or that line is missing, choose from `opus/medium` and "
        "`sonnet/high`. Prefer a different model from the parent's. Spawn one judge subagent on "
        "that model and tell it not to modify files.",
        1,
    ),
    # architect
    (
        "architect/SKILL.md",
        "line in the `pstack-models.mdc` rule, in place of the `arena runners` line. If the rule "
        "or that line is missing, use `claude-opus-5-5-xhigh` and `grok-4.7-xhigh-fast`. Alias and "
        "rejected entries follow",
        f"line in {CONFIG}, in place of the `arena runners` line. If the file or that line is "
        "missing, use `opus/medium` and `sonnet/high`. Value format and `inherit` entries follow",
        1,
    ),
    # interrogate
    (
        "interrogate/SKILL.md",
        "with the Task tool, one per entry on the `interrogate reviewers` line in `~/.cursor/rules/pstack-models.mdc`,",
        f"with the Agent tool, one per entry on the `interrogate reviewers` line in {CONFIG},",
        1,
    ),
    ("interrogate/SKILL.md", "If the rule or that line is missing", f"{LOADED} If the file or that line is missing", 1),
    ("interrogate/SKILL.md", "| `claude-opus-5-5-xhigh` |", "| `opus/medium` |", 1),
    ("interrogate/SKILL.md", "| `grok-4.7-xhigh-fast` |", "| `sonnet/high` |", 1),
    (
        "interrogate/SKILL.md",
        "Each reviewer gets `subagent_type: generalPurpose`, `readonly: true`, and `model` set to "
        "its configured entry, or its table default when there is no configured line. Omit `model` "
        "for an `auto` or `inherit-parent` entry, so that reviewer runs on the parent model.",
        'Each reviewer gets `subagent_type: "general-purpose"`, a brief that says not to modify '
        "files, and `model` and `effort` from its configured entry, or its table default when "
        f"there is no configured line. {VALUE_FORMAT} Omit both for an `inherit` entry, so that "
        "reviewer runs on the parent model.",
        1,
    ),
    (
        "interrogate/SKILL.md",
        re.compile(r"\nIf the Task tool rejects a configured entry, run that reviewer[^\n]*\n"),
        "",
        1,
    ),
    # swarm
    (
        "swarm/SKILL.md",
        "line in `~/.cursor/rules/pstack-models.mdc`. If the rule or that line is missing, use "
        "`grok-4.7-xhigh-fast`. For `auto` or `inherit-parent`, omit `model` so the workers run on "
        "the parent model. If the Task tool rejects a slug, use the default and say so. If it "
        "rejects the default, use the closest valid slug of the same family from its error message.",
        f"line in {CONFIG}. {LOADED} If the file or that line is missing, use `sonnet/medium`. "
        f"{VALUE_FORMAT} For `inherit`, omit both so the workers run on the parent model.",
        1,
    ),
    (
        "swarm/SKILL.md",
        "Spawn all N workers in one message with `subagent_type: generalPurpose`, "
        '`environment: "cloud"`, `run_in_background: true`, and the step 4 model, left unset for '
        '`auto` or `inherit-parent`. Use `environment: "local"` only when the worker needs access '
        "to something on the user's computer.",
        'Spawn all N workers in one message with `subagent_type: "general-purpose"`, '
        '`isolation: "worktree"` when they write, and the step 4 model and effort, left unset '
        'for `inherit`. Use `isolation: "remote"` instead only when cloud sessions are available '
        "and the worker needs nothing on the user's computer.",
        1,
    ),
    (
        "swarm/SKILL.md",
        "When a worker must start from a non-default pushed branch, pass `cloud_base_branch`.",
        "When a worker must start from a non-default branch, name it in the brief and have the "
        "worker check it out first.",
        1,
    ),
    # no-comments
    (
        "no-comments/SKILL.md",
        'Spawn `Task` with `subagent_type: "comment-sicko"`.',
        'Spawn an Agent with `subagent_type: "pstack:comment-sicko"`.',
        1,
    ),
    # verification skills
    ("create-verification-skill/SKILL.md", "`.cursor/skills/verify-<app>/", "`.claude/skills/verify-<app>/", 3),
    ("maintain-verification-skill/SKILL.md", "`.cursor/skills/verify-*/`", "`.claude/skills/verify-*/`", 1),
    # principles
    (
        "principle-type-system-discipline/SKILL.md",
        "For TypeScript syntax, see the `typescript-best-practices` skill.",
        "For language syntax, see that language's best-practices skill, such as `dev-workflow:python-best-practices`.",
        1,
    ),
    # Skills other skills invoke must be visible to the Skill tool.
    *[(f"{name}/SKILL.md", "\ndisable-model-invocation: true\n", "\n", 1) for name in MODEL_INVOKED],
]

# Cursor names the upstream adapter maps, from TERMS in scripts/generate-pstack-harness-trees.mjs,
# plus Cursor-isms it doesn't track. None may survive in the selected skills.
TERMS = {
    "Task": r"`Task`|\bTask (tool|subagent|call)",
    "AskQuestion": r"AskQuestion",
    "todolist": r"(?i:\btodo ?list\b)",
    "generalPurpose": r"generalPurpose",
    "poteto-agent": r"poteto-agent",
    "comment-sicko": r"(?<!pstack:)comment-sicko",
    "readonly": r"readonly: (true|false)|readonly/Ask|`readonly`",
    "environment": r"environment: \"(cloud|local)\"",
    "cloud_base_branch": r"cloud_base_branch",
    "run_in_background": r"run_in_background",
    "resume": r"`resume`",
    "file_attachments": r"file_attachments",
    "claude-": r"\bclaude-[a-z]+-\d",
    "grok-": r"\bgrok-\d",
    "gpt-": r"\bgpt-\d",
    "inherit-parent": r"inherit-parent",
    "pstack-models.mdc": r"pstack-models\.mdc",
    ".cursor/skills/": r"\.cursor/skills",
    "~/.cursor/plugins/": r"\.cursor/plugins|\.cursor-plugin",
    ".cursor/rules/": r"\.cursor/rules|always-applied rule",
    "agent-transcripts": r"agent-transcripts|\.cursor/projects",
    "Cursor-only features": r"Bugbot|Cursor [Aa]utomation|cursor\.(sh|com)/automations|[Cc]loud [Aa]gent|built-in PR tool",
    "Cursor": r"\bCursor\b|\.cursor/|mcps/|-xhigh|\bcreate-skill\b",
    "poteto-mode": r"poteto-mode",
    "unlinked principle": r"\*\*(?:principle-)?[a-z-]+\*\*(?: and \*\*[a-z-]+\*\*)? principle skills?|\*\*principle-[a-z-]+\*\*",
}

# Principle skills stay out of the model's skill list, so a reference to one becomes a link the agent can Read.
# "the **X** principle skill", "**X** and **Y** principle skills", or "**principle-X**".
PRINCIPLE_REF = re.compile(
    r"\*\*(?P<a>[a-z-]+)\*\*(?: and \*\*(?P<b>[a-z-]+)\*\*)? principle (?P<skills>skills?)"
    r"|\*\*principle-(?P<c>[a-z-]+)\*\*"
)
FORBIDDEN = re.compile("|".join(f"(?:{p})" for p in TERMS.values()))

# (path relative to pstack/skills, substring): example quotes in prompts, not instructions.
ALLOWED = (
    ("reflect/references/synthesizer.md", "Bugbot flagged regex backtracking"),
    ("reflect/references/synthesizer.md", "we renamed `gpt-4` to `gpt-4o`"),
)


def apply(text: str, old: str | re.Pattern[str], new: str, expected: int, label: str) -> str:
    if isinstance(old, re.Pattern):
        count = len(old.findall(text))
        if count == expected:
            return old.sub(new, text)
    else:
        count = text.count(old)
        if count == expected:
            return text.replace(old, new)
    if count == 0 and (not new or new in text):
        return text  # already applied
    sys.exit(f"{label}: expected {expected} match(es), found {count}")


def link_principles(path: Path, text: str) -> str:
    def link(name: str, label: str) -> str:
        target = SKILLS / f"principle-{name}" / "SKILL.md"
        if not target.exists():
            sys.exit(f"{path.relative_to(ROOT)}: no skill principle-{name}")
        return f"[{label}]({os.path.relpath(target, path.parent)})"

    def sub(m: re.Match[str]) -> str:
        if m["c"]:
            return link(m["c"], f"principle-{m['c']}")
        names = [n for n in (m["a"], m["b"]) if n]
        return " and ".join(link(n, n) for n in names) + (" principles" if len(names) > 1 else " principle")

    return PRINCIPLE_REF.sub(sub, text)


def allowed(path: Path, line: str) -> bool:
    rel = path.relative_to(SKILLS).as_posix() if path.is_relative_to(SKILLS) else ""
    return any(rel == p and s in line for p, s in ALLOWED)


def main() -> None:
    check = "--check" in sys.argv
    files: dict[Path, str] = {}
    for rel, old, new, expected in EDITS:
        path = SKILLS / rel
        files.setdefault(path, path.read_text())
        files[path] = apply(files[path], old, new, expected, rel)

    manifest = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())
    for skill in manifest["skills"]:
        for f in (ROOT / skill).rglob("*.md"):
            if f.is_relative_to(SKILLS):
                files[f] = link_principles(f, files.get(f, f.read_text()))

    changed = [p for p, t in files.items() if p.read_text() != t]
    if check:
        if changed:
            sys.exit("not applied: " + ", ".join(str(p.relative_to(ROOT)) for p in changed))
    else:
        for path in changed:
            path.write_text(files[path])

    leftovers = []
    for skill in manifest["skills"]:
        for f in (ROOT / skill).rglob("*.md"):
            for n, line in enumerate(f.read_text().splitlines(), 1):
                if FORBIDDEN.search(line) and not allowed(f, line):
                    leftovers.append(f"{f.relative_to(ROOT)}:{n}: {line[:120]}")
    if leftovers:
        sys.exit("Cursor-isms left in selected skills:\n" + "\n".join(leftovers))
    print(f"ok: {len(changed)} file(s) {'need changes' if check else 'rewritten'}")


if __name__ == "__main__":
    main()
