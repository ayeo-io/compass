---
description: Let a named agent approve for you
argument-hint: "<agent> until <time> [on <issues>] [for <forms>] [labels <labels>] [max <n>]"
disable-model-invocation: true
---

# /compass:delegate

The person typed this command. Compass's prompt hook has already acted on it
before you read this, and only the hook writes a delegation.

**When Compass's result is in your context**, say in one line what the
delegation covers and when it ends, then go on.

**When the hook blocked the command**, nothing reaches you; the person saw
why.

**When no Compass result is in your context**, the hook did not run: tell the
person that no delegation was made. Never create, extend or revoke a
delegation yourself.
