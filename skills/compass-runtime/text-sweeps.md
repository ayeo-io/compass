# Repository-wide text replacement

A rename touching many files is tempting to apply with one find-and-replace.
That method rewrites **data** as readily as prose, and the result is usually
valid - valid YAML, valid JSON, code that still runs - so nothing fails where
the mistake is. The vocabulary rename in ADR-023
(`architecture/decisions/ADR-023-the-vocabulary-is-measured-against-anthropics-docs.md`)
was applied that way and damaged twelve
things, two of them valid Python doing the wrong thing: a rename table that
gained `"x": "x"` and silently stopped migrating, and vendored third-party
code that `THIRD-PARTY-NOTICES.md` states is byte-identical to upstream.

Before any sweep:

1. **Exclude data by path** - rename tables, schema enums, generated pages,
   accepted decision records, vendored code, and quoted material whose hashes
   are checked elsewhere.
2. **Self-test input and output pairs before writing the first file.** It
   catches a wrong replacement, not one that is mechanically right and
   semantically wrong - which is why step 1 is the one that matters.
3. **Treat the left side of any mapping as data.** In `old: new`, rewriting
   `old` is how a migration quietly stops migrating.
   `tests/test_rename_tables_and_data_paths.py` guards this.

If the change can be applied file by file, do that instead.

