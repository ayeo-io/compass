# Security policy

## Reporting a vulnerability

Report a vulnerability privately through GitHub:
https://github.com/ayeo-io/compass/security/advisories/new

Do not open a public issue for it.

Include:

- the Compass version (`compass --version`);
- what an attacker can do, and what they need first;
- the steps to reproduce it.

You get a reply in the advisory. A fix ships as a new version, and the
advisory is published with it.

## Supported versions

Only the latest release gets security fixes, with one exception: Compass
8.x gets security fixes only, for 90 days after 9.0.0 is released. 9.0.0 was
released on 12 November 2026, so 8.x gets security fixes until 10 February
2027. After that, only 9.x is supported.

- Releases: https://github.com/ayeo-io/compass/releases
- Moving an 8.x project to 9.0.0: `docs/upgrade-9-0-0.md`

## What Compass runs

`docs/security.md` says what Compass runs, reads and sends, and what to
review before you install it.
