# Security policy

## Reporting a vulnerability

Report a vulnerability privately through GitHub:
https://github.com/ayeo-io/compass/security/advisories/new

Do not open a public issue for it. A public issue shows the problem to
everyone before a fix exists.

Include:

- the Compass version (`compass --version`);
- what an attacker can do, and what they need first;
- the steps to reproduce it.

You will get a reply in the advisory. A fix is released as a new version, and
the advisory is published with it.

## Supported versions

Only the latest release gets security fixes. Releases are listed at
https://github.com/ayeo-io/compass/releases.

## What Compass runs

`docs/security.md` describes what Compass runs, reads and sends, and what it
asks you to review before you install it. The README's section "What Compass
runs, sends and fetches" lists every outbound action.
