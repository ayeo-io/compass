"""The migrate map is parsed once per process, not once per manifest.

`normalize_spine` maps retired names forward for every manifest it reads,
through `migrate_map_section`, which parsed `cli/migrate-map.yml` on every
call. Reading this repository's 344 manifests parsed 1,546 YAML documents
(issue #353).

Scenario id: MM-1 (issue `migrate-map-parsed-once`).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))

from compass_pkg import core  # noqa: E402

MANIFEST = {"stages": {"frame": "full", "build": "full"},
            "gates": [{"id": "verify.fitness", "status": "pass"}]}


def _count_parses(monkeypatch):
    calls = []
    real = core.yaml.safe_load

    def counting(stream, *a, **k):
        calls.append(1)
        return real(stream, *a, **k)
    monkeypatch.setattr(core.yaml, "safe_load", counting)
    return calls


def test_mm_1_many_manifests_parse_the_map_once(monkeypatch):
    core.normalize_spine(dict(MANIFEST))   # warm, whatever ran before
    calls = _count_parses(monkeypatch)
    for _ in range(50):
        out = core.normalize_spine(dict(MANIFEST))
    assert out["stages"] == {"assess": "full", "implement": "full"}
    assert len(calls) == 0, len(calls)


def test_mm_1_a_changed_map_is_read_again(monkeypatch, tmp_path):
    copy = tmp_path / "migrate-map.yml"
    copy.write_text(Path(core.migrate_map_path()).read_text(encoding="utf-8"))
    monkeypatch.setattr(core, "migrate_map_path", lambda: str(copy))
    assert core._stage_key_renames()["frame"] == "assess"
    text = copy.read_text(encoding="utf-8").replace("frame: assess", "frame: plan")
    copy.write_text(text + "\n")
    assert core._stage_key_renames()["frame"] == "plan"
