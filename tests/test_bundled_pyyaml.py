"""Group G - the bundled copy and the machine it lands on.

- `TRC-G1`: whatever PyYAML the host machine has - none, one, or a different
  version - the CLI always resolves the copy Compass ships, deterministically.
- `TRC-G2`: the version that ships is the version the documentation names, and
  it is a specific version, not a range.
- `TRC-G3`: the bundled library carries its own licence and its attribution,
  and Compass's own licence is not changed to describe code Compass did not
  write.

This file also carries `DD-2`'s architecture check
(`test_every_yaml_reader_resolves_through_the_shared_mechanism`): the static
proof that nobody bypassed the one resolution mechanism. The dynamic tests
above prove the mechanism resolves correctly against a decoy; this proves
nobody wrote a seventh reader the old way. It is an architecture check in
the shape of `tests/test_house_style.py` - it adds no guardrail, no gate, no
vocabulary; `verify.architecture` is what it clears.
"""

# These tests assert the current file names; files written under older
# names still load (ADR-006).
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

FRAMEWORK_ROOT = Path(__file__).resolve().parent.parent
CLI_PATH = FRAMEWORK_ROOT / "cli" / "compass"
VENDOR_YAML = FRAMEWORK_ROOT / "cli" / "vendor" / "yaml"
PINNED_VERSION = "6.0.2"

_DECOY_SOURCE = (
    "__version__ = '0.0.0-decoy-not-the-bundled-copy'\n"
    "def safe_load(*a, **k):\n"
    "    raise AssertionError('the decoy yaml module was called - the CLI did "
    "not resolve the bundled copy')\n"
)


def _make_decoy(tmp_path: Path) -> Path:
    """A `yaml` package on its own directory, with a version no real release
    of PyYAML would ever report, so a resolver that picked it up is
    unmistakable in the output."""
    decoy_dir = tmp_path / "decoy-site"
    pkg = decoy_dir / "yaml"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text(_DECOY_SOURCE, encoding="utf-8")
    return decoy_dir


def _run_version(extra_env: dict) -> str:
    env = dict(os.environ)
    env.update(extra_env)
    proc = subprocess.run(
        [sys.executable, str(CLI_PATH), "--version"],
        capture_output=True, text=True, env=env, timeout=10,
    )
    assert proc.returncode == 0, proc.stderr
    return proc.stdout


def test_trc_g1_bundled_copy_wins_over_a_decoy(tmp_path):
    """A decoy `yaml` on PYTHONPATH, and the real system PyYAML still behind
    it in site-packages (on a machine that has one): the CLI reports the
    bundled version and a file location under `cli/vendor/yaml/`, not the
    decoy's, and not site-packages'. Run twice, same answer both times."""
    decoy_dir = _make_decoy(tmp_path)

    first = _run_version({"PYTHONPATH": str(decoy_dir)})
    second = _run_version({"PYTHONPATH": str(decoy_dir)})

    assert "0.0.0-decoy-not-the-bundled-copy" not in first, first
    assert PINNED_VERSION in first, first
    assert "cli/vendor/yaml" in first or "cli\\vendor\\yaml" in first, first
    assert first == second


def test_trc_g1_bundled_copy_wins_with_no_pythonpath_at_all(tmp_path):
    """The same resolution, with no PYTHONPATH set - the ordinary case for
    everyone who never had a decoy or a system PyYAML in play."""
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    proc = subprocess.run(
        [sys.executable, str(CLI_PATH), "--version"],
        capture_output=True, text=True, env=env, timeout=10,
    )
    assert proc.returncode == 0, proc.stderr
    assert PINNED_VERSION in proc.stdout, proc.stdout
    assert "cli/vendor/yaml" in proc.stdout, proc.stdout


def _copy_cli_tree(tmp_path: Path) -> Path:
    """A standalone copy of cli/ - compass, compass_pkg/, vendor/ - so a test
    can delete or corrupt the vendored tree without touching the real one."""
    dest = tmp_path / "cli-copy"
    shutil.copytree(FRAMEWORK_ROOT / "cli", dest)
    return dest


def _run_version_in_copy(cli_dir: Path, extra_env: dict | None = None):
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [sys.executable, str(cli_dir / "compass"), "--version"],
        capture_output=True, text=True, env=env, timeout=10,
    )


def test_trc_g1_absent_vendor_does_not_silently_fall_back_to_a_system_pyyaml(tmp_path):
    """Precedence is claimed unconditionally (ADR-013 Decision 3, `DD-3`): the
    bundled copy always wins, never a fallback. Inserting a nonexistent
    directory at sys.path[0] is a no-op, so with cli/vendor/ removed on a
    machine that also has a real PyYAML in site-packages, the resolver must
    refuse rather than quietly hand back the system copy. This is exactly the
    machine population the issue exists to serve: an adopter who followed the
    old by-hand install instruction and has a partial or missing plugin
    copy."""
    cli_dir = _copy_cli_tree(tmp_path)
    shutil.rmtree(cli_dir / "vendor")

    result = _run_version_in_copy(cli_dir)

    assert result.returncode == 3, result.stdout + result.stderr
    combined = result.stdout + result.stderr
    assert "site-packages" not in combined, (
        f"a system PyYAML answered instead of failing:\n{combined}")
    assert str((cli_dir / "vendor" / "yaml").resolve()) in combined, (
        f"the failure does not name the absolute path it checked:\n{combined}")
    assert "absent" in combined.lower() or "does not exist" in combined.lower(), (
        f"the failure does not distinguish 'absent' from 'broken':\n{combined}")


def test_trc_g1_corrupted_vendor_does_not_silently_fall_back_to_a_system_pyyaml(tmp_path):
    """The tree is present but damaged - one source file missing - rather
    than absent. The resolver must still refuse, and its message must not
    claim the copy is missing when it is actually broken (a corrupted
    install and an absent one are different failures with different fixes)."""
    cli_dir = _copy_cli_tree(tmp_path)
    (cli_dir / "vendor" / "yaml" / "parser.py").unlink()

    result = _run_version_in_copy(cli_dir)

    assert result.returncode == 3, result.stdout + result.stderr
    combined = result.stdout + result.stderr
    assert "site-packages" not in combined, (
        f"a system PyYAML answered instead of failing:\n{combined}")
    assert str((cli_dir / "vendor" / "yaml").resolve()) in combined, (
        f"the failure does not name the absolute path it checked:\n{combined}")
    assert ("damaged" in combined.lower() or "broken" in combined.lower()
            or "corrupt" in combined.lower()), (
        f"the failure does not distinguish 'broken' from 'absent':\n{combined}")
    assert "absent" not in combined.lower() and "does not exist" not in combined.lower(), (
        f"a present-but-broken tree was reported as absent:\n{combined}")


def test_trc_g2_bundled_version_matches_what_is_documented():
    """The version reported at runtime, the version recorded in
    THIRD-PARTY-NOTICES.md, and the version the vendored source itself
    declares all agree, and it is one exact version, not a range."""
    init_text = (VENDOR_YAML / "__init__.py").read_text(encoding="utf-8")
    m = re.search(r"__version__\s*=\s*['\"]([^'\"]+)['\"]", init_text)
    assert m, "cli/vendor/yaml/__init__.py has no __version__"
    shipped_version = m.group(1)
    assert shipped_version == PINNED_VERSION

    notices = (FRAMEWORK_ROOT / "THIRD-PARTY-NOTICES.md").read_text(encoding="utf-8")
    assert f"**Version:** {PINNED_VERSION}" in notices, notices
    # a range would look like "6.0" or "^6.0.2" or "6.0.*" - the notice must
    # name one exact version, not a family of them.
    assert re.search(r"\bVersion:\*\*\s*6\.0\.2\b(?!\.\d)", notices), notices

    stdout = _run_version({})
    assert PINNED_VERSION in stdout, stdout


def test_trc_g3_licence_and_attribution_present():
    """The bundled library's own licence text is in the distributed files,
    unmodified, and the repository states which files are third-party,
    whose they are, and at what version."""
    licence_path = FRAMEWORK_ROOT / "cli" / "vendor" / "LICENSE-PyYAML"
    assert licence_path.is_file()
    licence_text = licence_path.read_text(encoding="utf-8")
    assert "MIT" in licence_text or "Permission is hereby granted" in licence_text

    notices = (FRAMEWORK_ROOT / "THIRD-PARTY-NOTICES.md").read_text(encoding="utf-8")
    assert "PyYAML" in notices
    assert PINNED_VERSION in notices
    assert "pypi.org/project/PyYAML" in notices
    assert "d584d9ec91ad65861cc08d42e834324ef890a082e591037abe114850ff7bbc3e" in notices
    assert "MIT" in notices
    assert "cli/vendor/yaml" in notices
    assert "unmodified" in notices.lower() or "not modified" in notices.lower()

    vendor_readme = (FRAMEWORK_ROOT / "cli" / "vendor" / "README.md")
    assert vendor_readme.is_file()


def test_trc_g3_compass_licence_not_altered_to_describe_third_party_code():
    """Compass's own LICENSE describes Compass's own code, and continues to -
    PyYAML's terms live beside its code, not folded into Compass's licence
    file."""
    licence_text = (FRAMEWORK_ROOT / "LICENSE").read_text(encoding="utf-8")
    assert "Apache License" in licence_text
    assert "PyYAML" not in licence_text
    assert "MIT" not in licence_text


# ---------------------------------------------------------------------------
# The repository architecture check (DD-2) - nobody bypassed the shared mechanism
# ---------------------------------------------------------------------------

# Any spelling of a YAML import: `import yaml`, `import sys, yaml`,
# `import yaml as y`, `from yaml import safe_load`. A bare `grep "import
# yaml"` misses the comma form, which is how a YAML reader goes unnoticed -
# `scripts/integrate.sh` writes `import yaml, datetime, sys`.
_IMPORT_YAML_RE = re.compile(
    r"^[ \t]*(?:import[ \t]+[ \t\w,]*\byaml\b(?:[ \t]+as[ \t]+\w+)?[ \t]*(?:#.*)?$"
    r"|from[ \t]+yaml\b[ \t]+import\b)",
    re.MULTILINE,
)

# A heredoc opener: `<invoker> - <<'DELIM'` or `<invoker> - <<DELIM`, the
# shape every shell reader in this repository uses. Captures the invoking
# token (must be `compass_python`, not a bare `python3`) and the delimiter,
# so each heredoc's own body can be isolated rather than treating the whole
# file as one undifferentiated blob.
# Matched per line (^...$ under MULTILINE), because the invoker and the
# heredoc redirect always share one physical line in this codebase, however
# much sits between them: `hit="$(compass_python - "$cfg" "$rel" <<'PYEOF'`
# has two quoted arguments between the invoker and the redirect, and
# `( compass_python - <<PYEOF` has none. `.*?` (non-greedy) covers both
# without also matching an unrelated `-` earlier on the same line.
_HEREDOC_OPEN_RE = re.compile(
    r"^(?!\s*#)"  # not a comment line - a shell comment describing this
                  # exact pattern (`hooks/pre-tool.sh` has one) would
                  # otherwise be read as a real heredoc opener
    r".*?\b(?P<invoker>[A-Za-z_][\w.]*)[ \t]+-[ \t]+.*?<<-?[ \t]*"
    r"['\"]?(?P<delim>\w+)['\"]?[ \t]*.*$",
    re.MULTILINE,
)


def _iter_heredocs(text):
    """Yield (invoker, body_start, body_end) for each heredoc in `text`, in
    the order they open. Several heredocs in this repository reuse the same
    delimiter; the parser searches for each heredoc's closing line only
    after that heredoc's own body begins, so it never matches an earlier
    heredoc's close."""
    pos = 0
    for m in _HEREDOC_OPEN_RE.finditer(text):
        if m.start() < pos:
            continue  # inside a heredoc body already yielded - not a real opener
        nl = text.find("\n", m.end())
        if nl == -1:
            continue
        body_start = nl + 1
        end_re = re.compile(r"^" + re.escape(m.group("delim")) + r"\b", re.MULTILINE)
        end_m = end_re.search(text, body_start)
        body_end = end_m.start() if end_m else len(text)
        yield m.group("invoker"), body_start, body_end
        pos = body_end


def _find_yaml_reader_violations(file_texts: dict) -> list:
    """`file_texts` maps a repo-relative path to its text. Returns
    `path:line` for every YAML import that does not resolve through the one
    shared mechanism (DD-2): inside `cli/compass_pkg/` (the package's own
    `__init__` covers every submodule), the one entry point `cli/compass`
    (which imports `compass_pkg` first, explicitly), or a heredoc invoked
    through `compass_python` whose OWN body opens `import compass_pkg`
    before its own `import yaml`. Vendored third-party source is exempt - it
    is not subject to Compass's own resolution rule.

    Checked per heredoc, not per file: a `.sh` file with two heredocs (both
    hooks in this repository have exactly that shape) routes each one
    independently. A file's first heredoc doing the right thing does not
    excuse its second - `import compass_pkg` earlier in the FILE is not the
    same claim as `import compass_pkg` earlier in the SAME heredoc's body,
    and only the second is what `DD-2` actually promises."""
    violations = []
    for rel, text in file_texts.items():
        if rel in ("cli/compass",) or rel.startswith("cli/compass_pkg/"):
            continue
        if rel.startswith("cli/vendor/"):
            continue
        if rel.startswith("hooks/py/") and rel.endswith(".py"):
            # A hook's program file, run through `compass_python` as its
            # here-document was: its own text must import compass_pkg first.
            for m in _IMPORT_YAML_RE.finditer(text):
                if "import compass_pkg" not in text[:m.start()]:
                    violations.append(f"{rel}:{text.count(chr(10), 0, m.start()) + 1}")
            continue
        if not rel.endswith(".sh"):
            for m in _IMPORT_YAML_RE.finditer(text):
                line_no = text.count("\n", 0, m.start()) + 1
                violations.append(f"{rel}:{line_no}")
            continue

        heredocs = list(_iter_heredocs(text))
        for m in _IMPORT_YAML_RE.finditer(text):
            line_no = text.count("\n", 0, m.start()) + 1
            containing = next(
                ((inv, start, end) for inv, start, end in heredocs
                 if start <= m.start() < end),
                None,
            )
            if containing is None:
                # A yaml import outside any heredoc body in a shell script -
                # a bare `python3 -c "import yaml"` or similar, not routed
                # through anything.
                violations.append(f"{rel}:{line_no}")
                continue
            invoker, body_start, body_end = containing
            if invoker != "compass_python":
                violations.append(f"{rel}:{line_no}")
                continue
            body_before_import = text[body_start:m.start()]
            if "import compass_pkg" not in body_before_import:
                violations.append(f"{rel}:{line_no}")
    return violations


def test_yaml_reader_detection_flags_a_bypass_and_clears_the_shared_mechanism():
    """Unit-level proof of the detector itself, against synthetic fixtures -
    each shape a real reader could take."""
    routed_shell = (
        "#!/usr/bin/env bash\n"
        "source scripts/lib/compass-python.sh\n"
        "compass_python - <<'PY'\n"
        "import compass_pkg\n"
        "import yaml\n"
        "PY\n"
    )
    bypassing_shell = (
        "#!/usr/bin/env bash\n"
        "python3 - <<'PY'\n"
        "import sys, yaml\n"
        "PY\n"
    )
    bypassing_python = "import yaml\n\ndef f():\n    return yaml.safe_load('')\n"
    package_python = "import yaml\n"  # legitimately inside cli/compass_pkg/

    # One file, two heredocs: the first routed correctly, the second a
    # bypass. A per-file check sees the first import and passes the
    # second; this must not.
    mixed_two_heredoc_file = (
        "#!/usr/bin/env bash\n"
        "source scripts/lib/compass-python.sh\n"
        "a=$(compass_python - <<'PY'\n"
        "import compass_pkg\n"
        "import yaml\n"
        "PY\n"
        ")\n"
        "b=$(python3 - <<'PY'\n"
        "import sys, yaml\n"
        "PY\n"
        ")\n"
    )

    violations = _find_yaml_reader_violations({
        "scripts/lib/routed.sh": routed_shell,
        "scripts/lib/bypassing.sh": bypassing_shell,
        "scripts/rogue_reader.py": bypassing_python,
        "cli/compass_pkg/rogue.py": package_python,
        "cli/compass": "import compass_pkg\nimport yaml\n",
        "cli/vendor/yaml/__init__.py": "import io, re\nfrom .error import *\n",
        "scripts/mixed.sh": mixed_two_heredoc_file,
    })

    assert violations == [
        "scripts/lib/bypassing.sh:3",
        "scripts/rogue_reader.py:1",
        "scripts/mixed.sh:9",
    ]


def test_every_yaml_reader_resolves_through_the_shared_mechanism():
    """The real repository, scanned for real: every tracked file outside
    `tests/` that imports yaml in any spelling routes through `DD-2`'s one
    mechanism. A new reader written the old way fails this build."""
    listing = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=str(FRAMEWORK_ROOT), capture_output=True, text=True, check=True,
    ).stdout.splitlines()

    file_texts = {}
    for rel in listing:
        if rel.startswith("tests/"):
            continue
        full = FRAMEWORK_ROOT / rel
        if not full.is_file():
            continue
        try:
            file_texts[rel] = full.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue

    violations = _find_yaml_reader_violations(file_texts)
    assert not violations, (
        "these YAML imports do not resolve through the shared mechanism "
        "(scripts/lib/compass-python.sh + cli/compass_pkg/__init__.py) - "
        "name the helper in the failure and fix the reader:\n  "
        + "\n  ".join(violations)
    )


# ---------------------------------------------------------------------------
# cli/vendor/ contents - the invariant ADR-013 and cli/vendor/README.md both
# state and neither checked
# ---------------------------------------------------------------------------

_VENDOR_ALLOWED_ENTRIES = {"yaml", "LICENSE-PyYAML", "README.md"}


def _vendor_shadow_violations(vendor_dir: Path) -> list:
    """`cli/vendor/` sits at sys.path[0] in every Compass process (DD-2),
    ahead of the standard library itself - so only names that are not
    already in the standard library may ever be vendored there (ADR-013
    Decision 1, technical-design.md `DD-1` Consequences, `cli/vendor/README.md`: "Nothing
    else goes in this directory"). Returns a problem string per violation:
    an entry outside the declared allowlist, or an importable top-level name
    that collides with a standard-library module."""
    problems = []
    stdlib = set(getattr(sys, "stdlib_module_names", ()))
    for p in sorted(vendor_dir.iterdir()):
        if p.name == "__pycache__":
            # Not tracked by git and not part of what ships (see the audit
            # instruction in THIRD-PARTY-NOTICES.md, which excludes it the
            # same way) - a normal side effect of running Python against
            # cli/vendor/, not a violation of the allowlist.
            continue
        if p.name not in _VENDOR_ALLOWED_ENTRIES:
            problems.append(f"{p.name}: not in the declared allowlist "
                            f"{sorted(_VENDOR_ALLOWED_ENTRIES)}")
        name = None
        if p.is_dir() and (p / "__init__.py").is_file():
            name = p.name
        elif p.suffix == ".py":
            name = p.stem
        if name and name in stdlib:
            problems.append(f"{p.name}: shadows the standard library's "
                            f"'{name}' module")
    return problems


def test_vendor_shadow_detection_flags_a_stdlib_name_and_clears_an_honest_tree(tmp_path):
    """Unit-level proof of the detector, against a synthetic directory - a
    vendored package that happens to be named after a standard-library
    module (`json`), which position 0 would shadow for the whole CLI."""
    honest = tmp_path / "honest-vendor"
    honest.mkdir()
    (honest / "yaml").mkdir()
    (honest / "yaml" / "__init__.py").write_text("", encoding="utf-8")
    (honest / "LICENSE-PyYAML").write_text("", encoding="utf-8")
    (honest / "README.md").write_text("", encoding="utf-8")
    assert _vendor_shadow_violations(honest) == []

    shadowing = tmp_path / "shadowing-vendor"
    shadowing.mkdir()
    (shadowing / "yaml").mkdir()
    (shadowing / "yaml" / "__init__.py").write_text("", encoding="utf-8")
    (shadowing / "LICENSE-PyYAML").write_text("", encoding="utf-8")
    (shadowing / "README.md").write_text("", encoding="utf-8")
    (shadowing / "json.py").write_text("", encoding="utf-8")  # shadows stdlib json
    (shadowing / "notes.txt").write_text("", encoding="utf-8")  # not allowlisted

    violations = _vendor_shadow_violations(shadowing)
    assert any("json.py" in v and "shadows" in v for v in violations), violations
    assert any("notes.txt" in v and "allowlist" in v for v in violations), violations


def test_cli_vendor_only_holds_pyyaml_and_shadows_nothing_in_the_stdlib():
    """The real cli/vendor/ directory, checked for real."""
    violations = _vendor_shadow_violations(FRAMEWORK_ROOT / "cli" / "vendor")
    assert not violations, (
        "cli/vendor/ violates its own stated invariant (ADR-013 Decision 1, "
        "cli/vendor/README.md: 'nothing else goes in this directory'):\n  "
        + "\n  ".join(violations)
    )
