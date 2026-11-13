"""The architecture docs name every CLI path that reads templates/.

The one reader, the layered `compass policy lint`, went with the configuration
layers in 9.0.0 (ADR-094), so no CLI path reads a template and the docs say so."""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
READERS = set()
# Code that joins the folder name "templates" onto a path.
JOINS_TEMPLATES = re.compile(r"""["']templates["']""")


def _readers(root):
    found = set()
    cli = os.path.join(root, "cli")
    for folder, dirs, files in os.walk(cli):
        dirs[:] = [d for d in dirs if d not in ("vendor", "__pycache__")]
        for name in files:
            full = os.path.join(folder, name)
            if name.endswith(".py") or name == "compass":
                with open(full, encoding="utf-8") as fh:
                    if JOINS_TEMPLATES.search(fh.read()):
                        found.add(os.path.relpath(full, root))
    return found


def _doc(name):
    with open(os.path.join(ROOT, "architecture", name), encoding="utf-8") as fh:
        return fh.read()


def test_no_cli_path_reads_templates():
    assert _readers(ROOT) == READERS


def test_scan_reports_a_third_reader(tmp_path):
    extra = tmp_path / "cli" / "compass_pkg"
    extra.mkdir(parents=True)
    (extra / "third.py").write_text('p = os.path.join(ROOT, "templates", "x.md")\n')
    assert _readers(str(tmp_path)) == {"cli/compass_pkg/third.py"}


def test_docs_say_no_cli_path_reads_templates():
    for name in ("ownership.md", "relations.md"):
        text = _doc(name)
        for path in READERS:
            assert path in text, f"{name} does not name {path}"
        assert "policy_lint.py" not in text, name
        assert "not consumed" not in text
        assert "never read" not in text

