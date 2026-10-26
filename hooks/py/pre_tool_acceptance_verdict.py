# Run by hooks/pre-tool.sh: the guardrail that acceptance criteria exist before the code.
# The hook passes its arguments on the command line; standard input is closed.

import sys
import compass_pkg
from compass_pkg import stable_ids, word_map
try:
    import yaml
    with open(sys.argv[1], encoding="utf-8") as fh:
        task = yaml.safe_load(fh) or {}
    if not isinstance(task, dict):
        raise ValueError
except Exception:
    # Exit 0 means ALLOW, and that is deliberate: an unreadable or missing
    # manifest falls back to the behavior this hook had before the check
    # existed, rather than inventing a block. A false block on unreadable
    # state trains people to bypass the hook, which costs more than the case
    # it would catch. Pinned by
    # tests/test_hook_enforces_g2.py::test_scn_f1_an_unreadable_spine_does_not_block.
    # Any non-zero status below is the check being unable to RUN (a broken
    # install), which is a different thing from the manifest being
    # unreadable.
    sys.exit(0)
stages = task.get("stages") or task.get("phases") or {}  # vocabulary-scan: allow - reads the key an archived pre-v2 manifest holds
# Read both: `define` is the current key, and archived manifests still carry
# the pre-v2 `specify`. Reading one key only would switch the guardrail off
# for every migrated manifest.
if isinstance(stages, dict):
    weight = stages.get("define", stages.get("specify"))
    # The mode is read through the retired-word table, so a manifest written
    # before the depth words were renamed (`full`) and one written after
    # (`thorough`) both enforce. Comparing the raw value with one word would
    # stop matching the other with no error, and the guardrail would be off.
    weight = word_map.map_manifest({"stages": {"define": weight}})["stages"]["define"]
    if weight == stable_ids.MODE_THOROUGH and not (task.get("scenarios") or []):
        print("block")
        sys.exit(0)
# The issues this one waits for (ADR-062). Only this reader has the manifest
# parsed already, so it says whether the dependency reader below needs to run:
# an issue with no `depends_on`, or an empty one, starts no process for it. A
# value that is not a list says so too, so the dependency reader can warn.
if task.get("depends_on") not in (None, []):
    print("depends")
