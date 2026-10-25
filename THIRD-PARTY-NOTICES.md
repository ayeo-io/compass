# Third-party notices

Compass is Apache-2.0 licensed (see `LICENSE`). This file lists the
third-party code redistributed inside the plugin, so a reader or an auditor
can find its licence terms in one place.

## PyYAML

- **Package:** PyYAML
- **Version:** 6.0.2
- **Upstream:** https://pypi.org/project/PyYAML/
- **Source archive:** `pyyaml-6.0.2.tar.gz`
- **sha256:** `d584d9ec91ad65861cc08d42e834324ef890a082e591037abe114850ff7bbc3e`
- **Licence:** MIT (full text at `cli/vendor/LICENSE-PyYAML`)
- **Path in this repository:** `cli/vendor/yaml/`
- **Vendored copy:** unmodified - the vendored files are byte-identical to
  `lib/yaml/` inside the sdist above. Run each line below in order, from the
  repository root, to reproduce and compare. This is the only copy of the
  command in the repository: `cli/vendor/README.md` and `docs/security.md`
  point here rather than repeating it.

  ```
  pip download pyyaml==6.0.2 --no-binary :all: --no-deps -d /tmp/pyyaml-src
  shasum -a 256 /tmp/pyyaml-src/pyyaml-6.0.2.tar.gz   # compare with the sha256 above
  tar xzf /tmp/pyyaml-src/pyyaml-6.0.2.tar.gz -C /tmp/pyyaml-src
  diff -r -x __pycache__ /tmp/pyyaml-src/pyyaml-6.0.2/lib/yaml cli/vendor/yaml   # expect no output
  ```

  `pip download` only saves the archive; it does not extract it, so the
  `tar` step has to run before the `diff` can see a `lib/yaml/` directory
  to compare against. `-x __pycache__` excludes the bytecode cache Python
  writes into `cli/vendor/yaml/` the first time this CLI runs on this
  machine - real, but not part of what was vendored, and not tracked by
  git.

This is the CLI's only third-party dependency; everything else Compass
ships is the Python 3 standard library. See `cli/vendor/README.md` for how
every entry point resolves this copy, and `docs/security.md` for the audit
steps this notice supports.
