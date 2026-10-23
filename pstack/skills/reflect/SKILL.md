---
name: reflect
description: Spawn three parallel review subagents over the active transcript, surface learnings, and route each to a concrete edit on an existing skill. Use when the user says reflect.
disable-model-invocation: true
---

# Reflect

Mine the current conversation for durable learnings, then route them into skill edits.

Invoke when the user says "reflect" or "/reflect". Skip when the conversation is trivial, off-topic, or already covered by an existing skill the parent followed correctly. One-offs are not learnings.

## 1. Locate the active transcript

Before fanning out, find this conversation's transcript in `~/.claude/projects/<slug>/`, where `<slug>` is the absolute working directory with every non-alphanumeric character replaced by `-`. Call that directory `<transcripts>`. Do not glob across `~/.claude/projects/*/`. That crosses workspace boundaries and reads private chats from unrelated projects.

```bash
ls -t <transcripts>/*.jsonl <transcripts>/*/subagents/*.jsonl 2>/dev/null | head -10
```

That covers the session (`<id>.jsonl`) and subagent (`<id>/subagents/<child>.jsonl`) layouts. For each candidate, find the first line with `"type": "user"`. Take the file whose `message.content` contains the conversation's opening user prompt. If none matches, pass a tight digest of the session instead.

## 2. Spawn three reviewers in parallel

One message, three Agent calls, `subagent_type: "general-purpose"`. Reviewers need MCP access to look up the tickets, chat threads, and observability traces the transcript references, which `general-purpose` keeps.

Each reviewer and the synthesizer name a role line in `~/.claude/rules/pstack-models.md` and a default. Claude Code loads that file into every session, so read it only if its lines are not in context. A value is `<model>/<effort>`, e.g. `sonnet/high`: pass them as the Agent tool's `model` and `effort`. Use the default if the file or the line is missing. Leave both unset when the value is `inherit`. Raise or lower a subagent's `effort` to fit the job, but keep its `model`.

| Lens | Role line | Default `model` | Prompt template |
|---|---|---|---|
| Judgment | `reflect judgment, divergent, synthesizer` | `opus/medium` | `references/judgment-reviewer.md` |
| Tooling | `reflect tooling` | `sonnet/medium` | `references/tooling-reviewer.md` |
| Divergent | `reflect judgment, divergent, synthesizer` | `opus/medium` | `references/divergent-reviewer.md` |

Pass each template verbatim, substituting the transcript path or digest where marked. Reviewers return findings in the Agent result.

## 3. Synthesize

One Agent call, `subagent_type: "general-purpose"`, `model` and `effort` from the `reflect judgment, divergent, synthesizer` line (default `opus/medium`). It spot-verifies citations through MCP, which `general-purpose` keeps. Pass `references/synthesizer.md` verbatim, with each reviewer's full output inlined where marked. It returns an Accepted / Rejected / Backlog list.

## 4. Structural enforcement check

Move any Accepted item that a lint rule, script, metadata flag, or runtime check would enforce more reliably to Backlog. See the [encode-lessons-in-structure](../principle-encode-lessons-in-structure/SKILL.md) principle.

## 5. Apply

Present the synthesizer's full Accepted / Rejected / Backlog output and wait for explicit approval before applying any Accepted edit. The user picks the subset and may redirect routings. Skill changes affect every future agent in the org. Do not auto-apply.

File each Backlog item to your team's devex or backlog tracker without waiting. Only the Accepted list waits for approval.

Follow each approved row's Routing exactly:

- Trivial existing-skill edit (a one-line bullet, a tightened sentence, a stale fact corrected): the parent does it directly.
- Substantive existing-skill edit (a new section, a new pattern table, more than ~10 lines): hand to the `skill-creator` skill (edit directly if it isn't installed) and run its draft / test / iterate loop.
- `tune description: <skill path>` (the skill exists but didn't trigger when it should have): hand to `skill-creator` and run its description-optimization loop.
- `new skill via skill-creator: <kebab-name>`: hand creation to `skill-creator`. Do not invent the shape ad hoc.

If your environment ships a SKILL.md validator, run it on every touched skill before declaring done.

## 6. Summarize for the user

Short list, no preamble:

- Edits applied: `<skill path>`. What changed, one line each.
- New skills created: `<skill path>`. One line each (rare).
- Backlog filed to the devex tracker: `<issue title>` (`<tags>`). One line each.
- Dropped: one line per rejected finding + reason from the synthesizer.
