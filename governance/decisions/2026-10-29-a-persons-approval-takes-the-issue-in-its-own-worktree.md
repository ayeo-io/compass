# a-persons-approval-takes-the-issue-in-its-own-worktree

## Decided by

jed72

## Date

2026-10-29

## Supersedes

Nothing. It narrows the owner's answer of 2026-10-23 in the delegation-everywhere issue (requirements review Q6: "a slug held by two worktrees is refused"), which was not a decision entry.

## Decision

When a person types `/compass:approve --issue` or `/compass:reject --issue` in a worktree that holds the issue, the approval goes to that worktree's record, even when another worktree also holds the issue. An agent's delegated approval and `/compass:delegate --on` still refuse a slug that two worktrees hold, and a person's command is still refused when the worktree it is typed in does not hold the issue and two others do.

## Why

An issue triaged on `main` is committed there and then worked in a worktree, so two trees hold its record, and the person could not record the sign-off that irreversible work needs at all. A person types the command in one worktree after being shown the request, so their choice names one record. The refusal stays for agents for two reasons: identical words run by agents in two trees must not name two issues, and a copy that appears after a delegation named the issue must not receive that delegation's approvals.

The risk this accepts: a person who types the command in a worktree whose copy is stale, or was copied there, answers that copy. The text shown before the answer names the issue but not the folder.

## Evidence

ayeo-io/compass-delivery#317 [Approval refused when an issue's record is also on main]; jed72 chose "a person's approval only" (option B) over the current worktree winning everywhere, 2026-10-29, in conversation.
