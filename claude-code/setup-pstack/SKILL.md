---
name: setup-pstack
description: Configure which model and reasoning effort pstack uses per role. Writes ~/.claude/rules/pstack-models.md, which Claude Code loads into every session and the skills use instead of their defaults. Use for /setup-pstack, "configure pstack models", "pstack budget", or changing pstack's model choices.
disable-model-invocation: true
---

# Setup pstack

Write `~/.claude/rules/pstack-models.md`, the per-role model file that `how`, `why`, `reflect`, `arena`, `architect`, `interrogate`, and `swarm` use when spawning subagents. Claude Code loads every `.md` file in `~/.claude/rules/` into each new session, so the skills find the role lines in context.

## Values

A value is `<model>/<effort>`:

- model: `haiku`, `sonnet`, `opus`, or `fable`, the Agent tool's `model` aliases.
- effort: `low`, `medium`, `high`, `xhigh`, or `max`, the Agent tool's `effort`.

`inherit` means the role runs on the parent session's model and effort.

Panel roles (`arena runners`, `architect runners`, `interrogate reviewers`) take a comma-separated list. One subagent runs per entry, `inherit` entries included, so the list length sets the count. `arena cross-judge pool` is also a list, but arena picks one entry, preferring a model different from the parent's.

## Steps

### 1. Load current state

If `~/.claude/rules/pstack-models.md` exists, read it. Otherwise read the old location, `~/.claude/pstack-models.md`, if it exists. Treat its `# budget` line and role values as the current choices. Otherwise start from the defaults in step 4. Drop any line whose role is not in step 4 and tell the user.

### 2. Ask for a budget

Ask in plain text, one question, and wait for the answer. Offer these options and name the current one:

- `unlimited`: every effort `max`
- `large`: every effort one step up from the defaults
- `default`: the defaults in step 4
- `small`: every effort one step down from the defaults, never below `low`

The budget moves effort only, never the model. Keep any role the user set by hand on a re-run, and leave `inherit` untouched.

### 3. Show and confirm

Show every role with its resulting value as a table. Ask whether to accept as-is or change specific roles. Take changes one at a time in plain text, validating each against the values above. Repeat until the user accepts.

### 4. Write the file

Overwrite the whole file so re-runs stay idempotent. No frontmatter, so it applies to every session. Shape, with the defaults:

```
# pstack model configuration. One line per role. Delete a line to fall back to the skill default.
# Value: <model>/<effort>, or `inherit` for the parent session's model. Lists: one subagent per entry.
# budget: default
how explorer: haiku/high
how explainer: opus/medium
why investigators: haiku/high
why synthesizer: opus/medium
reflect tooling: sonnet/medium
reflect judgment, divergent, synthesizer: opus/medium
arena runners: opus/medium, sonnet/high
arena cross-judge pool: opus/medium, sonnet/high
architect runners: opus/medium, sonnet/high
interrogate reviewers: opus/medium, sonnet/high
swarm workers: sonnet/medium
```

### 5. Confirm

Tell the user the file was written and that it applies to new sessions. If `~/.claude/pstack-models.md` exists, tell the user nothing reads it anymore and offer to delete it. Re-running this skill updates the file.
