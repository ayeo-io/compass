<!--
TEMPLATE: devlog.md
Produced by: opened at assess, appended to at every stage transition and
             notable event, closed at ship time. Hooks write to it too -
             `hooks/post-tool.sh` appends entries after code edits.
Lives at:    .compass/work/<issue-slug>/devlog.md
Role in the pipeline: the append-only running log. Persistence over
conversation - if it isn't on disk, it didn't happen. A later session, or
a different agent, reconstructs the issue's history from this file plus
delivery-approach.md.

APPEND-ONLY. Never edit or delete a past entry. Newest entries go at the
bottom. One entry per stage transition or notable event. Keep each entry
short - what happened, evidence pointer, what's next.
-->

# Devlog - {{ISSUE_SLUG}}

> **Issue:** {{ONE-LINE DESCRIPTION}} · **Opened:** {{DATE}}
> Append-only. Newest at the bottom.

---

## {{YYYY-MM-DD HH:MM}} - Assess

- **Event:** assess ran; the delivery approach was computed.
- **Approach:** {{reference shape - quick fix/regular/full/hotfix/spike}} - see `delivery-approach.md` revision {{N}}.
- **Assessment:** risk {{…}}, familiarity {{…}}, size {{…}}, goal & role {{…}}.
- **Policy rules fired:** {{list - or "none"}}.
- **Owed follow-ups:** {{list - or "none" (a spike owes none)}}.
- **Next:** define acceptance criteria {{or explore, on a spike}}.

## {{YYYY-MM-DD HH:MM}} - Define

- **Event:** {{scenarios authored \| existing behaviour mapped first, then new scenarios authored}}.
- **Artifact:** `acceptance-criteria.md` - {{N}} scenarios in {{M}} groups.
- **Next:** {{requirements review \| plan, if the review collapsed}}.

## {{YYYY-MM-DD HH:MM}} - {{Requirements review | Plan | Breakdown | Implement | Verify}}

- **Event:** {{what happened}}.
- **Artifact:** {{which file written/updated}}.
- **Evidence:** {{pointer to the evidence record, e.g. `evidence/green-TRC-3.json`}}.
- **Next:** {{next stage}}.

<!-- Notable-event entries (not stage transitions) look like this: -->
## {{YYYY-MM-DD HH:MM}} - note: {{SHORT TITLE}}

- **Event:** {{e.g. "re-assessment triggered - implementation revealed the size was small, not atomic"}}.
- **Detail:** {{what changed and why}}.

<!-- Hook-written entries (post-tool.sh) look like this: -->
## {{YYYY-MM-DD HH:MM}} - edit: {{path/to/file}}

- **Tool:** {{Edit \| Write}} · **Red marker:** {{present \| cleared - tests now pass}}.

## {{YYYY-MM-DD HH:MM}} - Ship

- **Event:** issue closed.
- **What shipped:** {{summary}}.
- **How checked:** {{pointer to verification-report.md gate decision}}.
- **Follow-ups settled:** {{list - for a hotfix, the root-cause line goes here}}.
- **Follow-ups filed:** {{issue ids - or "none"}}.
