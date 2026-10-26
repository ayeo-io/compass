"""The text a hook runs, as one string: the script, the parts it sources from
hooks/lib/ in order, and the programs it runs from hooks/py/.

Tests that read a hook's source read it through this, so a check of what the
hook does still sees the code after it moved into a part or a program file.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PART = re.compile(r'^\. "\$PRE_TOOL_PARTS/([\w.-]+\.sh)"$', re.M)
PROGRAM = re.compile(r"hooks/py/([\w.-]+\.py)")


def parts(script):
    """The hooks/lib/ parts the script sources, in order."""
    text = Path(script).read_text(encoding="utf-8")
    return [ROOT / "hooks" / "lib" / name for name in PART.findall(text)]


def hook_text(script):
    """The script, then its parts, then each program they run, once each."""
    shell = [Path(script).read_text(encoding="utf-8")]
    shell += [part.read_text(encoding="utf-8") for part in parts(script)]
    names = dict.fromkeys(name for text in shell for name in PROGRAM.findall(text))
    programs = [(ROOT / "hooks" / "py" / name).read_text(encoding="utf-8") for name in names]
    return "\n".join(shell + programs)


def hook_sources():
    """Every file of hook code: the hook scripts, their parts in hooks/lib/
    and the programs in hooks/py/. A scan of what the hooks do or print reads
    all of them, so code that moved into a part or a program is still read."""
    hooks = ROOT / "hooks"
    return (sorted(hooks.glob("*.sh")) + sorted((hooks / "lib").glob("*.sh"))
            + sorted((hooks / "py").glob("*.py")))


def copy_hooks(tree, replacements=()):
    """Copy hooks/ into `tree`, then replace each `old` text by its `new`, once,
    in the one file of the pre-tool hook that holds it: the script, one of its
    parts or one of the programs in hooks/py/. Returns the copied script's path."""
    import shutil

    shutil.copytree(ROOT / "hooks", tree / "hooks",
                    ignore=shutil.ignore_patterns("__pycache__"))
    script = tree / "hooks" / "pre-tool.sh"
    files = [script] + [tree / "hooks" / "lib" / p.name for p in parts(ROOT / "hooks" / "pre-tool.sh")]
    files += sorted((tree / "hooks" / "py").glob("*.py"))
    for old, new in dict(replacements).items():
        holders = [f for f in files if old in f.read_text(encoding="utf-8")]
        assert len(holders) == 1, f"hooks/pre-tool.sh and its parts hold {old!r} {len(holders)} times"
        text = holders[0].read_text(encoding="utf-8")
        holders[0].write_text(text.replace(old, new, 1), encoding="utf-8")
    return script
