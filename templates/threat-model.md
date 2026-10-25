<!--
TEMPLATE: threat-model.md
Written when the assessment carries `auth`, `payments` or `personal-data` (RP-REQUIRE-005).

THE FOUR QUESTIONS BELOW ARE NOT OURS. They are the Threat Modeling
Manifesto's (threatmodelingmanifesto.org), verbatim, from a fifteen-person
working group including Adam Shostack and Izar Tarandach. Do not reword them:
a paraphrase is a fork of a standard with none of its authority.

THE THIRD ANSWER IS A SCENARIO ID, NOT PROSE. The Manifesto names the failure
this prevents - "Admiration for the Problem", a document that lists threats
and mitigates none. A threat here is answered by a `TRC-` id in
acceptance-criteria.md, which the framework then forces a test on and traces.
A threat you are deliberately not acting on is written `risk accepted` with
the reason - a decision rather than a shrug. `compass check` reports any row
that is neither.

The ThoughtWorks Technology Radar has had threat modeling in Adopt since
Nov 2015 and names the same output form: "evil user stories".

REVISIT IT. The Radar's warning is the "security sandwich" - threat modeling
done once at the start and never again. Re-run this when the design changes.

Keep it under 120 lines. Delete this comment block when you fill it in.
-->

# Threat model - {{ISSUE_SLUG}}

<!-- compass:render document-header -->
<!-- /compass:render -->

## What are we working on?

<!-- Two or three sentences, or a sketch. What is in scope, what is not, and
     where the trust boundary sits. If a diagram helps, a mermaid block here
     beats a paragraph. -->

{{The change, and the boundary it touches.}}

## What can go wrong?

<!-- One row per threat. STRIDE is a useful prompt list if the room goes
     quiet - spoofing, tampering, repudiation, information disclosure, denial
     of service, elevation of privilege - but it is a prompt, not a form to
     complete.

     Do not fill the "what are we going to do" column with prose. Either a
     scenario id, or `risk accepted` and why. -->

| Threat | What are we going to do about it? |
|---|---|
| {{A forged session token is accepted as valid}} | {{`TRC-B4`}} |
| {{An expired token is accepted after a clock skew}} | {{`TRC-B5`}} |
| {{The audit log is filled by repeated failed logins}} | {{risk accepted - the platform rotates it hourly and alerts on volume}} |

## What are we going to do about it?

<!-- The scenarios named above, written out in acceptance-criteria.md. This
     section is a pointer, not a second copy: two lists of the same thing
     drift, and the one in acceptance-criteria.md is the one that gets
     tested. -->

The scenarios above are in `acceptance-criteria.md`. {{Anything the scenarios
cannot express - a dependency to upgrade, an alert to add, a runbook entry -
goes here with an owner.}}

## Did we do a good enough job?

<!-- The Manifesto's fourth question, and Compass already answers it: this is
     the evidence gate. Do not grade your own work here - point at what ran.

     If a threat above has no scenario and no accepted risk, the honest answer
     to this question is "not yet", and `compass check` will say so. -->

| Threat | Scenario | Evidence |
|---|---|---|
| {{A forged session token is accepted}} | {{`TRC-B4`}} | {{`EV-T-TRC-B4`}} |

{{What is still open, and when this will be re-run.}}
