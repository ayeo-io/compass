# Technical design - refusal-template-follow-ups

One subtask: `hooks/pre-tool.sh`, `cli/compass_pkg/refusals.py`,
`docs/refusal-codes.md`, `scripts/install.sh`, `scripts/multiagent.sh`
and their tests.

- RTF-1: `emit_refusal` prints the three fallback lines whenever the
  render fails, naming the target and tool from its own `target=` and
  `tool=` arguments, then python3's output, if any, indented beneath.
- RTF-2: the texts in `REFUSALS`.
- RTF-3: `render()` cuts any parameter to 20 words, marking the cut.
- RTF-4: the call-site test matches `emit_refusal <code>`,
  `compass_block <code>` or `render("<code>"`; the scan test calls the
  scan function; the comment is corrected; the 3.9 test is skipped when
  no such python3 exists.
- RTF-5: `scripts/install.sh` and `scripts/multiagent.sh`; the scan adds
  `scripts/*.sh`.
- RTF-6: the page's claim, the fixture, the test comment, the idiom.
