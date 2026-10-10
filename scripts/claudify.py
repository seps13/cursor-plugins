#!/usr/bin/env python3
"""Rewrite the selected pstack skills for Claude Code.

Replaces Cursor-isms (Task tool, generalPurpose, readonly, cloud workers,
~/.cursor paths, grok/xhigh model slugs) with Claude Code equivalents, and
points model lookup at ~/.claude/pstack-models.md, written by the
Claude Code setup-pstack in claude-code/setup-pstack/.

Every replacement asserts its expected match count, so an upstream wording
change fails loudly instead of silently leaving a Cursor-ism behind.

Upstream bump: rebase seps13-patches onto the new upstream, drop the old
"Apply claudify.py" commit, run this script, commit the result.

Usage: python3 scripts/claudify.py [--check]
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / "pstack" / "skills"

CONFIG = "`~/.claude/pstack-models.md`"
VALUE_FORMAT = (
    "A value is `<model>/<effort>`, e.g. `sonnet/high`: pass them as the Agent tool's "
    "`model` and `effort`."
)
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
    f"a role line in {CONFIG} and a default. Read that file once. {VALUE_FORMAT} Use the "
    "default if the file or the line is missing. Leave both unset when the value is `inherit`."
)

# (path relative to pstack/skills, old, new, expected count). Literal unless old is re.Pattern.
EDITS: list[tuple[str, str | re.Pattern[str], str, int]] = [
    # how
    ("how/SKILL.md", OLD_ROLE_RULE_TAIL, NEW_ROLE_RULE_TAIL, 1),
    (
        "how/SKILL.md",
        "- `subagent_type`: `generalPurpose`\n"
        "- `model`: the `how explorer` line, default `grok-4.7-xhigh-fast`\n"
        "- `readonly`: `true`",
        "- `subagent_type`: `Explore`\n"
        "- `model`: the `how explorer` line, default `haiku/high`",
        1,
    ),
    (
        "how/SKILL.md",
        "- `subagent_type`: `generalPurpose`\n"
        "- `model`: the `how explainer` line, default `claude-opus-5-5-xhigh`\n"
        "- `readonly`: `true`",
        "- `subagent_type`: `general-purpose`\n"
        "- `model`: the `how explainer` line, default `opus/medium`\n"
        "- Read-only: tell it not to modify files",
        2,
    ),
    ("how/SKILL.md", "one Task subagent", "one subagent", 2),
    # why
    ("why/SKILL.md", OLD_ROLE_RULE_TAIL, NEW_ROLE_RULE_TAIL, 1),
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
        "- `subagent_type`: `generalPurpose`\n"
        "- `model`: the `why investigators` line, default `grok-4.7-xhigh-fast`\n"
        "- `readonly`: `false` (agent mode). **Do not use readonly/Ask mode.** It strips MCP "
        "access, which disables MCP-backed investigators entirely. Investigators still shouldn't "
        "write anything.",
        "- `subagent_type`: `general-purpose`\n"
        "- `model`: the `why investigators` line, default `haiku/high`\n"
        "- Investigators shouldn't write anything. Say so in the prompt.",
        1,
    ),
    (
        "why/SKILL.md",
        "- `subagent_type`: `generalPurpose`\n"
        "- `model`: the `why synthesizer` line, default `claude-opus-5-5-xhigh`\n"
        "- `readonly`: `false` (agent mode). The synthesizer's quality check spot-verifies "
        "citations, which can require MCP access. Readonly/Ask mode strips MCPs and defeats that.",
        "- `subagent_type`: `general-purpose`\n"
        "- `model`: the `why synthesizer` line, default `opus/medium`",
        1,
    ),
    # reflect
    ("reflect/SKILL.md", OLD_ROLE_RULE_TAIL, NEW_ROLE_RULE_TAIL, 1),
    (
        "reflect/SKILL.md",
        "The system prompt names the active workspace's `agent-transcripts/` directory. Use that "
        "path. Do not glob across `~/.cursor/projects/*/`.",
        f"Claude Code stores it under {TRANSCRIPT_DIR}. Call that directory `<agent-transcripts>`. "
        "Do not glob across `~/.claude/projects/*/`.",
        1,
    ),
    (
        "reflect/SKILL.md",
        "Three transcript layouts: legacy flat (`<id>.jsonl`), current nested (`<id>/<id>.jsonl`), "
        "and subagent (`<parent>/subagents/<child>.jsonl`).",
        "Two transcript layouts: session (`<id>.jsonl`) and subagent "
        "(`<id>/subagents/<child>.jsonl`).",
        1,
    ),
    (
        "reflect/SKILL.md",
        "read the first JSONL line and check that `message.content[0].text` contains",
        "find the first line with `\"type\": \"user\"` and check that its `message.content` "
        "contains",
        1,
    ),
    (
        "reflect/SKILL.md",
        "One message, three `Task` calls, `subagent_type: generalPurpose`, with `model` set as "
        "below, agent mode (`readonly: false`).",
        "One message, three Agent calls, `subagent_type: general-purpose`, with `model` and "
        "`effort` set as below.",
        1,
    ),
    ("reflect/SKILL.md", " Readonly strips MCPs.", "", 2),
    ("reflect/SKILL.md", "in the `Task` response body", "in the Agent result", 1),
    (
        "reflect/SKILL.md",
        "One `Task` call, `subagent_type: generalPurpose`, with `model` from the",
        "One Agent call, `subagent_type: general-purpose`, with `model` and `effort` from the",
        1,
    ),
    ("reflect/SKILL.md", ", agent mode (`readonly: false`).", ".", 1),
    ("reflect/SKILL.md", "`claude-opus-5-5-xhigh`", "`opus/medium`", 3),
    ("reflect/SKILL.md", "`grok-4.7-xhigh-fast`", "`sonnet/medium`", 1),
    (
        "reflect/SKILL.md",
        "hand to Cursor's built-in `create-skill` skill and run its draft / test / iterate loop.",
        "hand to the `skill-creator` skill if installed and run its draft / test / iterate loop. "
        "Otherwise edit directly.",
        1,
    ),
    *[
        (
            f"reflect/references/{name}.md",
            "(workspace `.cursor/skills/`, user-level `~/.cursor/skills/`, or plugin-installed "
            "paths under `~/.cursor/plugins/`)",
            "(project `.claude/skills/`, user-level `~/.claude/skills/`, or plugin-installed "
            "paths under `~/.claude/plugins/`)",
            1,
        )
        for name in ("judgment-reviewer", "tooling-reviewer", "divergent-reviewer")
    ],
    *[
        (f"reflect/references/{name}.md", "- `Task` prompts", "- Agent prompts", 1)
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
    # arena
    (
        "arena/SKILL.md",
        "Use the `arena runners` line in `~/.cursor/rules/pstack-models.mdc`. If the rule or that "
        "line is missing, default to one each on `claude-opus-5-5-xhigh` and `grok-4.7-xhigh-fast`. "
        "An `auto` or `inherit-parent` entry in this line or the cross-judge line means the parent "
        "model, so omit `model` for it. If the Task tool rejects a configured entry, run that seat "
        "on its family's default and say so. Families go by prefix: `claude-*` and `grok-*`. With "
        "no family match, use `claude-opus-5-5-xhigh`. If it rejects a default, use the closest "
        "valid slug of the same family from its error message.",
        f"Use the `arena runners` line in {CONFIG}. If the file or that line is missing, default "
        f"to one each on `opus/medium` and `sonnet/high`. {VALUE_FORMAT} An `inherit` entry in "
        "this line or the cross-judge line means the parent model, so omit both for it.",
        1,
    ),
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
        "using the Task tool. Use the `interrogate reviewers` line in "
        "`~/.cursor/rules/pstack-models.mdc`",
        f"using the Agent tool. Use the `interrogate reviewers` line in {CONFIG}",
        1,
    ),
    ("interrogate/SKILL.md", "If the rule or that line is missing", "If the file or that line is missing", 1),
    ("interrogate/SKILL.md", "| `claude-opus-5-5-xhigh` |", "| `opus/medium` |", 1),
    ("interrogate/SKILL.md", "| `grok-4.7-xhigh-fast` |", "| `sonnet/high` |", 1),
    (
        "interrogate/SKILL.md",
        "- `subagent_type`: `generalPurpose`\n"
        "- `model`: the configured `interrogate reviewers` entry, or the table default with no "
        "configured line. For an `auto` or `inherit-parent` entry, omit `model` so that reviewer "
        "runs on the parent model.\n"
        "- `readonly`: `true`",
        "- `subagent_type`: `general-purpose`\n"
        "- `model` and `effort`: the configured `interrogate reviewers` entry (`<model>/<effort>`), "
        "or the table default with no configured line. For an `inherit` entry, omit both so that "
        "reviewer runs on the parent model.\n"
        "- Read-only: tell it not to modify files",
        1,
    ),
    (
        "interrogate/SKILL.md",
        re.compile(r"\nIf the Task tool rejects a configured entry, run that reviewer[^\n]*\n"),
        "",
        1,
    ),
    # swarm
    ("swarm/SKILL.md", "N parallel cloud workers", "N parallel workers", 1),
    ("swarm/SKILL.md", "not the cloud concurrency limit", "not a concurrency limit", 1),
    (
        "swarm/SKILL.md",
        "line in `~/.cursor/rules/pstack-models.mdc`. If the rule or that line is missing, use "
        "`grok-4.7-xhigh-fast`. For `auto` or `inherit-parent`, omit `model` so the workers run on "
        "the parent model. If the Task tool rejects a slug, use the default and say so. If it "
        "rejects the default, use the closest valid slug of the same family from its error message.",
        f"line in {CONFIG}. If the file or that line is missing, use `sonnet/medium`. "
        f"{VALUE_FORMAT} For `inherit`, omit both so the workers run on the parent model.",
        1,
    ),
    (
        "swarm/SKILL.md",
        "Spawn all N workers in one message with `subagent_type: generalPurpose`, "
        "`environment: \"cloud\"`, `run_in_background: true`, and the step 4 model, left unset for "
        "`auto` or `inherit-parent`. Use `environment: \"local\"` only when the worker needs access "
        "to something on the user's computer.",
        "Spawn all N workers in one message with `subagent_type: general-purpose`, "
        "`isolation: \"worktree\"` when they write, `run_in_background: true`, and the step 4 "
        "model and effort, left unset for `inherit`. Use `isolation: \"remote\"` instead only when "
        "cloud sessions are available and the worker needs nothing on the user's computer.",
        1,
    ),
    (
        "swarm/SKILL.md",
        "When a worker must start from a non-default pushed branch, pass `cloud_base_branch`.",
        "When a worker must start from a non-default branch, name it in the brief and have the "
        "worker check it out first.",
        1,
    ),
    # verification skills
    ("create-verification-skill/SKILL.md", "`.cursor/skills/verify-<app>/", "`.claude/skills/verify-<app>/", 3),
    ("maintain-verification-skill/SKILL.md", "`.cursor/skills/verify-*/`", "`.claude/skills/verify-*/`", 1),
]

# Must not survive anywhere in the selected skills.
FORBIDDEN = re.compile(
    r"pstack-models\.mdc|generalPurpose|`readonly`|\.cursor/|Task tool|grok-|-xhigh|"
    r"inherit-parent|cloud_base_branch|environment: \"cloud\"|AskQuestion"
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


def main() -> None:
    check = "--check" in sys.argv
    files: dict[Path, str] = {}
    for rel, old, new, expected in EDITS:
        path = SKILLS / rel
        files.setdefault(path, path.read_text())
        files[path] = apply(files[path], old, new, expected, rel)

    changed = [p for p, t in files.items() if p.read_text() != t]
    if check:
        if changed:
            sys.exit("not applied: " + ", ".join(str(p.relative_to(ROOT)) for p in changed))
    else:
        for path in changed:
            path.write_text(files[path])

    manifest = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())
    leftovers = []
    for skill in manifest["skills"]:
        for f in (ROOT / skill).rglob("*.md"):
            for n, line in enumerate(f.read_text().splitlines(), 1):
                if FORBIDDEN.search(line):
                    leftovers.append(f"{f.relative_to(ROOT)}:{n}: {line[:120]}")
    if leftovers:
        sys.exit("Cursor-isms left in selected skills:\n" + "\n".join(leftovers))
    print(f"ok: {len(changed)} file(s) {'need changes' if check else 'rewritten'}")


if __name__ == "__main__":
    main()
