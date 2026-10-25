<!--
TEMPLATE: incident.md
Produced by: whoever declares the incident - written at intake, before or
             alongside the hotfix work it triggers.
Lives at:    docs/compass/<created>-<issue-slug>/incident.md
Role in the pipeline: the intake artifact that triggers a hotfix. SRE sense
of the word: what broke in production, the impact, the severity. The hotfix
reproduces from this, ships expedited, and settles its follow-ups (promote
the reproduction into proper acceptance criteria; optional postmortem)
before the issue fully closes.

Fill every {{PLACEHOLDER}}.
-->

# Incident - {{ISSUE_SLUG}}

> **Issue type:** hotfix · **Declared:** {{DATE_TIME}} · **Declared by:** {{NAME / role}}
> **Severity:** {{SEV1 - user-facing outage | SEV2 - degraded | SEV3 - contained}}

## What broke

{{The failure as observed in production - the alert, the error rate, the
user report. Paste the signal that raised it.}}

## Impact

{{Who is affected and how: users, data, money, obligations. Numbers where
you have them ("~4% of checkout requests since 09:12 UTC").}}

## Timeline

| Time (UTC) | What happened |
|---|---|
| {{HH:MM}} | {{first signal}} |
| {{HH:MM}} | {{declared / mitigated / resolved}} |

## Immediate mitigation

{{What was done to limit the impact before the fix - rollback, feature
flag off, traffic shift - or "none available", stated plainly.}}

## Follow-ups owed

- [ ] Reproduction promoted into proper acceptance criteria on the hotfix issue
- [ ] Postmortem ({{optional - decided at ship time}})
