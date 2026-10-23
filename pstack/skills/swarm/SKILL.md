---
name: swarm
description: "Fan out N parallel workers, drain them, and return one report. Use for /swarm, 'swarm this', or parallel coverage, races, gauntlets, and exploration."
disable-model-invocation: true
---

# Swarm

## Start

Open a TodoWrite list with one entry per phase before launching anything.

1. Frame
2. Fan out
3. Aggregate
4. Report

## Phase A: Frame

1. State the done predicate and the artifact or report the swarm must return.
2. Choose the shape. Partition into slices, race N workers on identical briefs, or mix both. For a race or mixed shape, declare `first pass`, `rank all`, or `best-of` before spawning.
4. Pick the worker model from the `swarm workers` line in `~/.claude/rules/pstack-models.md`. Claude Code loads that file into every session, so read it only if its lines are not in context. If the file or that line is missing, use `sonnet/medium`. A value is `<model>/<effort>`, e.g. `sonnet/high`: pass them as the Agent tool's `model` and `effort`. For `inherit`, omit both so the workers run on the parent model. For a model race, name each arm's model up front. Raise or lower a subagent's `effort` to fit the job, but keep its `model`.
5. Give each worker its own writable output when it writes. When workers verify or measure commits, each brief names the exact SHAs. A measurement brief also names the method (sample count, what one sample is, order). The worker records both in its result.

## Phase B: Fan out

Spawn all N workers in one message with `subagent_type: "general-purpose"`, `isolation: "worktree"` when they write, and the step 4 model and effort, left unset for `inherit`. Use `isolation: "remote"` instead only when cloud sessions are available and the worker needs nothing on the user's computer.

When a worker must start from a non-default branch, name it in the brief and have the worker check it out first.

Every brief stands alone. Include the goal, scope, exact slice or race arm, how to verify, and what to report. Reports use `PASS`, `ISSUES`, or `BLOCKED` with evidence. A worker that can prove a defect reports `ISSUES` and lists every issue it can prove, not only the first.

If a worker drops out, proceed with N-1 and note it.

## Phase C: Aggregate

Read the terminal results. Drop a result that does not record the SHAs and method its brief names, and respawn that worker once. After a second miss, record a gap. A gap does not count as a pass. For coverage, every required slice needs a result. For a race, apply the selection rule declared up front. Use first pass, rank all, or best-of. Do not paste raw worker dumps.

## Phase D: Report

Return one consolidated in-chat report with the table, issue one-liners, gaps or dropouts, and the race rule when used.
