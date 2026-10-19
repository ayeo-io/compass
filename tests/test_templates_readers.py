"""The architecture docs name every CLI path that reads templates/."""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
READERS = {
    "cli/compass_pkg/policy_lint.py",
    "cli/compass_pkg/template_lists.py",
}
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


def test_cli_reads_templates_through_two_paths():
    assert _readers(ROOT) == READERS


def test_scan_reports_a_third_reader(tmp_path):
    extra = tmp_path / "cli" / "compass_pkg"
    extra.mkdir(parents=True)
    (extra / "third.py").write_text('p = os.path.join(ROOT, "templates", "x.md")\n')
    assert _readers(str(tmp_path)) == {"cli/compass_pkg/third.py"}


def test_docs_name_both_reading_paths():
    for name in ("ownership.md", "relations.md"):
        text = _doc(name)
        for path in READERS:
            assert path in text, f"{name} does not name {path}"
        assert "not consumed" not in text
        assert "never read" not in text


def test_docs_say_template_show_skips_the_architecture_folder():
    assert "architecture/" in _doc("relations.md")
    assert "not listed" in _doc("relations.md")
