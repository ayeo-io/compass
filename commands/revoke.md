---
description: End delegated approvals now
argument-hint: "[DL-n]"
disable-model-invocation: true
---

# /compass:revoke

The person typed this command. Compass's prompt hook has already acted on it
before you read this.

**When Compass's result is in your context**, say which delegations ended.
From now on, do not run `compass evidence approve --delegated` under them.

**When no Compass result is in your context**, the hook did not run: tell
the person that nothing was revoked. Never edit a delegation yourself.
