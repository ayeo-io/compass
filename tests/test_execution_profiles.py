"""Execution profiles: the profile file, its digest, the store and the resolver.

Scenario ids EPM-1 to EPM-46 (issue execution-profile-manifests). A test name
starts with its scenario id. The fixtures are in tests/fixtures/execution-profiles/.
The commands are `compass profile lint`, `add` and `show`; their behaviour is
owned by docs/execution-profiles.md.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))
sys.path.insert(0, str(ROOT / "tests"))

import project_readiness_support as support  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "execution-profiles"
REQUIRED = ("id", "version", "digest", "parent", "owner", "approval", "applies_to",
            "runner_versions", "model", "components", "runner_settings")
STORE_FILE = re.compile(r"^[a-z][a-z0-9-]{0,63}\.[1-9][0-9]*\.yml$")


# --- helpers ---


def load_fixture(name):
    """The profile file of a fixture folder, as a mapping."""
    return yaml.safe_load((FIXTURES / name / "profile.yml").read_text(encoding="utf-8"))


def digest_of(data):
    """The digest of a profile mapping, worked out here and not by the code
    under test: canonical JSON of the content without `digest`."""
    body = {k: v for k, v in data.items() if k != "digest"}
    text = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return "sha256:" + hashlib.sha256(text.encode("ascii")).hexdigest()


def finish(data):
    """`data` with its own correct digest, so a test changes one thing only."""
    data["digest"] = digest_of(data)
    return data


def valid():
    return load_fixture("valid")


def put(folder, data, name="profile.yml"):
    """Write a profile mapping (or text, or bytes) to `folder/name`."""
    path = Path(folder) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, bytes):
        path.write_bytes(data)
    elif isinstance(data, str):
        path.write_text(data, encoding="utf-8")
    else:
        path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path


def make(tmp_path, fixture=None):
    """A fixture project. With `fixture`, its `profiles/` folder is copied in."""
    project = support.make_project(Path(tmp_path) / "project", commit=False)
    if fixture is not None and (FIXTURES / fixture / "profiles").is_dir():
        shutil.copytree(FIXTURES / fixture / "profiles", project / "profiles")
    return project


def store(project, data, name=None):
    """Put a profile in the store directly. Returns the stored path."""
    name = name or f"{data['id']}.{data['version']}.yml"
    return put(Path(project) / "profiles", data, name)


def store_files(project):
    folder = Path(project) / "profiles"
    if not folder.is_dir():
        return []
    return sorted(p.name for p in folder.iterdir() if STORE_FILE.match(p.name))


def profile(project, *argv):
    return support.run_compass(project, "profile", *argv)


def reason_lines(out):
    return [line for line in out.splitlines() if re.match(r"^[a-z][a-z-]*: ", line)]


def codes(out):
    return [line.split(":", 1)[0] for line in reason_lines(out)]


def no_trace(out, err):
    assert "Traceback" not in out + err, out + err


def lint_data(tmp_path, data, *flags):
    """Lint a mapping in a fresh project. Returns `(project, code, out, err)`."""
    project = make(tmp_path)
    path = put(project / "work", data)
    return (project, *profile(project, "lint", str(path), *flags))


# --- group A: format and schema ---


def test_epm_1_valid_profile_is_accepted_and_every_field_shown(tmp_path):
    project = make(tmp_path)
    path = put(project, valid())
    code, out, err = profile(project, "lint", str(path))
    assert code == 0, out + err
    data = valid()
    for name in REQUIRED:
        found = [line for line in out.splitlines() if re.match(rf"^\s*{name}:\s+\S", line)]
        assert found, (name, out)
    assert re.search(r"^\s*owner:\s+jed72\s*$", out, re.M)
    assert re.search(r"^\s*id:\s+lean-implement\s*$", out, re.M)
    assert data["digest"] in out
    assert "2 skills, 1 prompt fragments, 1 tool guidance" in out


def test_epm_2_missing_required_field_is_refused(tmp_path):
    for field in ("schema",) + REQUIRED:
        data = valid()
        del data[field]
        _, code, out, err = lint_data(tmp_path / field, data)
        assert code == 2, (field, out, err)
        lines = [line for line in reason_lines(out) if line.startswith("field-missing")]
        assert len(lines) == 1 and field in lines[0], (field, out)
        assert len(reason_lines(out)) == 1, (field, out)


def test_epm_3_empty_scope_is_refused(tmp_path):
    for name in ("task_classes", "repositories"):
        data = valid()
        data["applies_to"][name] = []
        _, code, out, _ = lint_data(tmp_path / name, finish(data))
        assert code == 2, out
        lines = [line for line in reason_lines(out) if line.startswith("scope-empty")]
        assert len(lines) == 1 and f"applies_to.{name}" in lines[0], out


def test_epm_4_malformed_value_is_refused(tmp_path):
    rows = [("id", "Lean_Implement"), ("id", "1-lean"), ("version", 0), ("version", 1.5),
            ("digest", "sha256:abc"), ("digest", "md5:0123"),
            ("runner_versions[0]", "7.0"), ("runner_settings.max_cycles", -1),
            ("runner_settings.max_minutes", 0), ("schema", 2), ("owner", ""),
            ("approval", "approved")]
    for index, (field, value) in enumerate(rows):
        data = valid()
        if field == "runner_versions[0]":
            data["runner_versions"][0] = value
        elif "." in field:
            head, tail = field.split(".")
            data[head][tail] = value
        else:
            data[field] = value
        _, code, out, err = lint_data(tmp_path / str(index), data)
        assert code == 2, (field, value, out, err)
        lines = [line for line in reason_lines(out) if line.startswith("field-malformed")
                 and field in line]
        assert lines, (field, value, out)
        if value != "":
            assert str(value) in lines[0], (field, value, lines)
        no_trace(out, err)


def test_epm_5_duplicate_component_is_refused(tmp_path):
    data = valid()
    data["components"]["skills"].append(
        {"id": "tdd-discipline", "revision": "sha256:" + "ab" * 32})
    _, code, out, _ = lint_data(tmp_path, finish(data))
    assert code == 2, out
    lines = [line for line in reason_lines(out) if line.startswith("component-duplicate")]
    assert len(lines) == 1 and "skill" in lines[0] and "tdd-discipline" in lines[0], out


def test_epm_6_revision_not_exact_is_refused(tmp_path):
    for index, revision in enumerate(("latest", "^1.2.0", "sha256:0123abc", "*")):
        data = valid()
        data["components"]["skills"][0]["revision"] = revision
        _, code, out, _ = lint_data(tmp_path / str(index), finish(data))
        assert code == 2, (revision, out)
        lines = [line for line in reason_lines(out) if line.startswith("revision-not-exact")]
        assert len(lines) == 1, (revision, out)
        assert "tdd-discipline" in lines[0] and revision in lines[0], lines


def test_epm_7_unknown_tier_or_effort_is_refused(tmp_path):
    from compass_pkg import model_tiers
    rows = (("tier", "ultra", "tier-unknown", model_tiers.TIERS),
            ("tier", "Standard", "tier-unknown", model_tiers.TIERS),
            ("effort", "extreme", "effort-unknown", model_tiers.EFFORTS))
    assert len(model_tiers.TIERS) == 3 and len(model_tiers.EFFORTS) == 5
    for index, (field, value, code_name, accepted) in enumerate(rows):
        data = valid()
        data["model"][field] = value
        _, code, out, _ = lint_data(tmp_path / str(index), finish(data))
        assert code == 2, out
        lines = [line for line in reason_lines(out) if line.startswith(code_name)]
        assert len(lines) == 1 and value in lines[0], out
        for name in accepted:
            assert name in lines[0], (name, lines[0])


def test_epm_8_unreadable_file_is_refused(tmp_path):
    text = yaml.safe_dump(valid(), sort_keys=False)
    faults = {
        "empty": b"",
        "bracket": text.replace("owner: jed72", "owner: [").encode(),
        "twice": (text + "owner: someone-else\n").encode(),
        "binary": bytes([0xff, 0xfe, 0x00, 0x80, 0x81]) * 8,
        "comment-only": b"# nothing here\n",
        "bare-text": b"abc\n",
    }
    for name, content in faults.items():
        project = make(tmp_path / name)
        path = put(project, content)
        code, out, err = profile(project, "lint", str(path))
        assert code == 2, (name, out, err)
        assert any(line.startswith("file-unreadable") and str(path) in line
                   for line in out.splitlines()), (name, out)
        no_trace(out, err)
    project = make(tmp_path / "absent")
    missing = project / "nope.yml"
    code, out, err = profile(project, "lint", str(missing))
    assert code == 2 and "file-unreadable" in out and str(missing) in out, out + err
    no_trace(out, err)
    folder = project / "folder"
    folder.mkdir()
    code, out, err = profile(project, "lint", str(folder))
    assert code == 2 and "file-unreadable" in out, out + err
    no_trace(out, err)


# --- group B: versions, digest and immutability ---


def test_epm_9_digest_mismatch_is_refused(tmp_path):
    data = valid()
    recorded = data["digest"]
    data["owner"] = "someone-else"
    _, code, out, _ = lint_data(tmp_path, data)
    assert code == 2, out
    lines = [line for line in reason_lines(out) if line.startswith("digest-mismatch")]
    assert len(lines) == 1, out
    computed = digest_of(data)
    assert recorded in lines[0] and computed in lines[0] and recorded != computed


def test_epm_10_same_content_same_digest(tmp_path):
    first = valid()
    shuffled = json.loads(json.dumps(first))
    text = yaml.safe_dump(shuffled, sort_keys=False)
    reordered = yaml.safe_dump(_reverse(shuffled), sort_keys=False)
    noisy = "# one\n\n# two\n" + reordered.replace("\n", "\n\n", 3) + "\n# three\n"
    project = make(tmp_path)
    one = put(project, text, "a.yml")
    two = put(project, noisy, "b.yml")
    results = []
    for path in (one, two):
        code, out, err = profile(project, "lint", "--json", str(path))
        assert code == 0, out + err
        results.append(json.loads(out))
    assert results[0]["computed_digest"] == results[1]["computed_digest"]
    assert results[0]["computed_digest"] == digest_of(first)


def _reverse(value):
    if isinstance(value, dict):
        return {k: _reverse(value[k]) for k in reversed(list(value))}
    if isinstance(value, list):
        return [_reverse(v) for v in value]
    return value


def test_epm_11_different_content_different_digest(tmp_path):
    def computed(data, where):
        _, code, out, err = lint_data(tmp_path / where, finish(data), "--json")
        assert code == 0, out + err
        return json.loads(out)["computed_digest"]

    base = computed(valid(), "base")
    changes = {}
    d = valid()
    d["components"]["skills"][0]["revision"] = "sha256:" + "cd" * 32
    changes["revision"] = d
    d = valid()
    d["owner"] = "another-owner"
    changes["owner"] = d
    d = valid()
    d["components"]["skills"].reverse()
    changes["order"] = d
    d = valid()
    d["runner_settings"]["max_cycles"] = 11
    changes["cycles"] = d
    d = valid()
    d["model"]["provider_revision"] = None
    changes["provider"] = d
    digests = {name: computed(data, name) for name, data in changes.items()}
    for name, value in digests.items():
        assert value != base, name
    assert len(set(digests.values())) == len(digests)


def test_epm_12_changed_profile_is_a_new_version(tmp_path):
    project = make(tmp_path, "changed")
    before = (project / "profiles" / "lean-implement.1.yml").read_bytes()
    v2 = put(project / "work", (FIXTURES / "changed" / "profile.yml").read_bytes())
    code, out, err = profile(project, "add", str(v2))
    assert code == 0, out + err
    assert store_files(project) == ["lean-implement.1.yml", "lean-implement.2.yml"]
    first = yaml.safe_load(before)
    second = yaml.safe_load((project / "profiles" / "lean-implement.2.yml").read_bytes())
    assert first["digest"] != second["digest"]
    assert (project / "profiles" / "lean-implement.1.yml").read_bytes() == before
    assert (project / "profiles" / "lean-implement.2.yml").read_bytes() == v2.read_bytes()


def test_epm_13_stored_version_is_immutable(tmp_path):
    project = make(tmp_path)
    original = valid()
    stored = store(project, original)
    before = stored.read_bytes()
    other = valid()
    other["owner"] = "someone-else"
    path = put(project / "work", finish(other))
    code, out, err = profile(project, "add", str(path))
    assert code == 2, out + err
    lines = [line for line in reason_lines(out) if line.startswith("version-immutable")]
    assert len(lines) == 1 and original["digest"] in lines[0], out
    assert stored.read_bytes() == before
    assert store_files(project) == ["lean-implement.1.yml"]


def test_epm_14_same_version_again_changes_nothing(tmp_path):
    project = make(tmp_path)
    stored = store(project, valid())
    before = stored.read_bytes()
    path = put(project / "work", yaml.safe_dump(_reverse(valid()), sort_keys=False))
    code, out, err = profile(project, "add", str(path))
    assert code == 0, out + err
    assert "already stored" in out
    assert store_files(project) == ["lean-implement.1.yml"]
    assert stored.read_bytes() == before


def test_epm_15_missing_parent_is_refused(tmp_path):
    project = make(tmp_path)
    data = valid()
    data["version"] = 2
    data["parent"] = {"version": 1, "digest": valid()["digest"]}
    path = put(project / "work", finish(data))
    code, out, err = profile(project, "add", str(path))
    assert code == 2, out + err
    lines = [line for line in reason_lines(out) if line.startswith("parent-missing")]
    assert len(lines) == 1 and "lean-implement" in lines[0] and "version 1" in lines[0], out
    assert store_files(project) == []


def test_epm_16_parent_digest_mismatch_is_refused(tmp_path):
    project = make(tmp_path)
    parent = valid()
    store(project, parent)
    data = valid()
    data["version"] = 2
    wrong = "sha256:" + "ef" * 32
    data["parent"] = {"version": 1, "digest": wrong}
    path = put(project / "work", finish(data))
    code, out, err = profile(project, "add", str(path))
    assert code == 2, out + err
    lines = [line for line in reason_lines(out) if line.startswith("parent-digest-mismatch")]
    assert len(lines) == 1 and parent["digest"] in lines[0] and wrong in lines[0], out
    assert store_files(project) == ["lean-implement.1.yml"]


def test_epm_17_version_not_next_is_refused(tmp_path):
    digest = valid()["digest"]
    rows = ((3, {"version": 1, "digest": digest}, 2), (2, None, 1),
            (1, {"version": 1, "digest": digest}, 2))
    for index, (version, parent, should) in enumerate(rows):
        project = make(tmp_path / str(index))
        store(project, valid())
        data = valid()
        data["version"], data["parent"] = version, parent
        path = put(project / "work", finish(data))
        code, out, err = profile(project, "add", str(path))
        assert code == 2, (version, out, err)
        lines = [line for line in reason_lines(out) if line.startswith("version-not-next")]
        assert len(lines) == 1 and f"must be version {should}" in lines[0], (version, out)
        assert store_files(project) == ["lean-implement.1.yml"]


def test_epm_18_edited_store_file_is_refused_when_shown(tmp_path):
    project = make(tmp_path, "valid")
    stored = store(project, valid())
    stored.write_text(stored.read_text(encoding="utf-8").replace("owner: jed72",
                                                                  "owner: jed73"),
                      encoding="utf-8")
    code, out, err = profile(project, "show", "lean-implement", "--version", "1")
    assert code == 2, out + err
    lines = [line for line in reason_lines(out) if line.startswith("digest-mismatch")]
    assert len(lines) == 1 and "lean-implement.1.yml" in lines[0], out
    for ref in valid()["components"]["skills"]:
        assert ref["revision"] not in out


def test_epm_46_refused_file_is_not_stored(tmp_path):
    def faults():
        data = valid()
        del data["owner"]
        yield "owner removed", data
        data = valid()
        data["runner_settings"]["max_cycles"] = 31
        yield "over ceiling", finish(data)
        data = valid()
        data["digest"] = data["digest"][:-1] + ("0" if data["digest"][-1] != "0" else "1")
        yield "digest changed", data

    for index, (label, data) in enumerate(faults()):
        project = make(tmp_path / str(index))
        path = put(project / "work", data)
        l_code, l_out, _ = profile(project, "lint", str(path))
        a_code, a_out, a_err = profile(project, "add", str(path))
        assert l_code == 2 and a_code == 2, (label, a_out, a_err)
        assert reason_lines(l_out) == reason_lines(a_out) != [], label
        assert store_files(project) == [], label


# --- group C: the resolver ---

KIND_OF = {"skills": "skill", "prompt_fragments": "prompt_fragment",
           "tool_guidance": "tool_guidance"}


def component_list(data):
    """`(kind, id, revision)` for every reference, in the order show must list them."""
    return [(KIND_OF[name], ref["id"], ref["revision"])
            for name in ("skills", "prompt_fragments", "tool_guidance")
            for ref in data["components"][name]]


def entry_for(kind, comp_id, revision, versions=("7.0.0",), state="approved"):
    entry = {"kind": kind, "id": comp_id, "revision": revision,
             "runner_versions": list(versions)}
    if state is not None:
        entry["approval"] = {"state": state, "by": "jed72", "at": "2026-10-22"}
    return entry


def registry_for(data, versions=("7.0.0",)):
    return [entry_for(k, i, r, versions) for k, i, r in component_list(data)]


def write_registry(project, entries):
    text = entries if isinstance(entries, str) else yaml.safe_dump(
        {"components": entries}, sort_keys=False)
    return put(Path(project) / "profiles", text, "component-registry.yml")


def compass_yml(project, models=None, extra=""):
    text = "schema: 1\nextends: compass:default@7\n" + extra
    if models:
        text += "models:\n" + "".join(f"  {t}: {m}\n" for t, m in models.items())
    (Path(project) / "compass.yml").write_text(text, encoding="utf-8")


def json_lines(out):
    """Reason lines out of a `--json` refusal, shaped as plain lines."""
    return "\n".join(f"{r['code']}: {r['message']}" for r in json.loads(out))


def shown(tmp_path, data=None, entries=None, models=None):
    """A project that stores `data` and a registry, and the `show --json` result."""
    data = data or valid()
    project = make(tmp_path)
    store(project, data)
    write_registry(project, registry_for(data) if entries is None else entries)
    if models:
        compass_yml(project, models)
    code, out, err = profile(project, "show", data["id"], "--version", str(data["version"]),
                             "--json")
    return project, code, out, err


def three_component_profile():
    data = valid()
    del data["components"]["skills"][1]
    return finish(data)


def test_epm_19_show_gives_exact_revisions(tmp_path):
    data = valid()
    project, code, out, err = shown(tmp_path, data)
    assert code == 0, out + err
    again = profile(project, "show", "lean-implement", "--version", "1", "--json")
    assert again[0] == 0 and again[1] == out
    doc = json.loads(out)
    listed = [(c["kind"], c["id"], c["revision"]) for c in doc["components"]]
    assert listed == component_list(data) and len(listed) == 4
    assert doc["model"]["tier"] == "standard" and doc["model"]["effort"] == "medium"
    assert doc["model"]["mapped_model"] == "sonnet"
    assert doc["model"]["provider_revision"] == "example-model-2026-10-01"
    assert doc["runner_settings"] == data["runner_settings"]


def test_epm_20_unknown_profile_is_refused(tmp_path):
    project = make(tmp_path)
    store(project, valid())
    write_registry(project, registry_for(valid()))
    # A valid profile file beside the store, which an id with a path in it would reach.
    put(project, valid(), "lean-implement.1.yml")
    for ident, version in (("lean-implement", "2"), ("other-profile", "1"),
                           ("../lean-implement", "1")):
        code, out, err = profile(project, "show", ident, "--version", version)
        assert code == 2, (ident, out, err)
        lines = [line for line in reason_lines(out) if line.startswith("profile-missing")]
        assert len(lines) == 1 and ident in lines[0] and f"version {version}" in lines[0], out
        for _, _, revision in component_list(valid()):
            assert revision not in out


def test_epm_21_show_needs_a_version(tmp_path):
    project = make(tmp_path)
    store(project, valid())
    second = valid()
    second["version"] = 2
    second["parent"] = {"version": 1, "digest": valid()["digest"]}
    store(project, finish(second))
    write_registry(project, registry_for(valid()))
    code, out, err = profile(project, "show", "lean-implement")
    assert code == 2, out + err
    assert codes(out) == ["version-required"], out
    for _, _, revision in component_list(valid()):
        assert revision not in out


def test_epm_22_missing_component_is_refused(tmp_path):
    project = make(tmp_path, "missing-component")
    data = load_fixture("missing-component")
    store(project, data)
    code, out, err = profile(project, "show", "lean-implement", "--version", "1")
    assert code == 2, out + err
    assert codes(out) == ["component-missing"], out
    line = reason_lines(out)[0]
    revision = data["components"]["prompt_fragments"][0]["revision"]
    assert "prompt_fragment" in line and "terse-status" in line and revision in line
    for ref in data["components"]["skills"] + data["components"]["tool_guidance"]:
        assert ref["revision"] not in out


def test_epm_23_other_revision_is_not_substituted(tmp_path):
    data = valid()
    revision_a = data["components"]["skills"][0]["revision"]
    revision_b = "sha256:" + "be" * 32
    entries = registry_for(data)
    entries[0]["revision"] = revision_b
    _, code, out, err = shown(tmp_path, data, entries)
    assert code == 2, out + err
    lines = json_lines(out).splitlines()
    assert [line.split(":")[0] for line in lines] == ["component-missing"], out
    assert revision_a in out and revision_b not in out


def test_epm_24_missing_or_empty_registry(tmp_path):
    data = three_component_profile()
    for name, registry in (("absent", None), ("no-entry", "components: []\n"),
                           ("empty-file", ""), ("no-key", "{}\n")):
        project = make(tmp_path / name)
        store(project, data)
        if registry is not None:
            write_registry(project, registry)
        code, out, err = profile(project, "show", "lean-implement", "--version", "1")
        assert code == 2, (name, out, err)
        assert codes(out) == ["component-missing"] * 3, (name, out)


def test_epm_25_not_approved_component_is_refused(tmp_path):
    for name, state in (("pending", "pending"), ("rejected", "rejected"), ("none", None)):
        data = valid()
        revision_a = data["components"]["tool_guidance"][0]["revision"]
        entries = registry_for(data)
        entries[-1] = entry_for("tool_guidance", "read-only-first", revision_a, state=state)
        entries.append(entry_for("tool_guidance", "read-only-first", "sha256:" + "11" * 32))
        _, code, out, err = shown(tmp_path / name, data, entries)
        assert code == 2, (name, out, err)
        lines = json_lines(out).splitlines()
        assert len(lines) == 1 and lines[0].startswith("component-not-approved"), (name, out)
        assert "read-only-first" in lines[0] and revision_a in lines[0]
        assert (state or "none") in lines[0]


def test_epm_26_incompatible_component_is_refused(tmp_path):
    project = make(tmp_path, "incompatible-component")
    store(project, load_fixture("incompatible-component"))
    code, out, err = profile(project, "show", "lean-implement", "--version", "1")
    assert code == 2, out + err
    assert codes(out) == ["component-incompatible"], out
    line = reason_lines(out)[0]
    assert "tdd-discipline" in line and "7.1.0" in line and "7.0.0" in line


def test_epm_27_every_refusal_is_reported(tmp_path):
    data = valid()
    data["runner_versions"] = ["7.0.0", "7.1.0"]
    data = finish(data)
    entries = registry_for(data, ("7.0.0", "7.1.0"))
    entries = [e for e in entries if e["id"] != "tdd-discipline"]
    for entry in entries:
        if entry["id"] == "evidence-gates":
            entry["approval"]["state"] = "pending"
        if entry["id"] == "terse-status":
            entry["runner_versions"] = ["7.0.0"]
    _, code, out, err = shown(tmp_path, data, entries)
    assert code == 2, out + err
    lines = json_lines(out).splitlines()
    assert [line.split(":")[0] for line in lines] == [
        "component-missing", "component-not-approved", "component-incompatible"], out
    named = ["tdd-discipline", "evidence-gates", "terse-status"]
    for line, name in zip(lines, named):
        assert name in line and "read-only-first" not in line, line


def test_epm_28_registry_duplicate_is_refused(tmp_path):
    data = valid()
    revision = data["components"]["skills"][0]["revision"]
    entries = registry_for(data)
    entries.append(entry_for("skill", "tdd-discipline", revision, state="pending"))
    _, code, out, err = shown(tmp_path, data, entries)
    assert code == 2, out + err
    lines = json_lines(out).splitlines()
    assert len(lines) == 1 and lines[0].startswith("registry-duplicate"), out
    assert "skill" in lines[0] and "tdd-discipline" in lines[0] and revision in lines[0]


def test_epm_45_unusable_registry_is_refused(tmp_path):
    data = valid()

    def broken(change):
        entries = registry_for(data)
        change(entries[0])
        return entries

    rows = {
        "not-yaml": ("components: [\n", "file-unreadable"),
        "no-kind": (broken(lambda e: e.pop("kind")), "field-missing"),
        "no-runners": (broken(lambda e: e.pop("runner_versions")), "field-missing"),
        "plugin-kind": (broken(lambda e: e.update(kind="plugin")), "field-malformed"),
        "latest": (broken(lambda e: e.update(revision="latest")), "field-malformed"),
        "text-approval": (broken(lambda e: e.update(approval="approved")), "field-malformed"),
    }
    for name, (entries, code_name) in rows.items():
        _, code, out, err = shown(tmp_path / name, data, entries)
        assert code == 2, (name, out, err)
        lines = json_lines(out).splitlines()
        assert [line.split(":")[0] for line in lines] == [code_name], (name, out)
        assert "component-registry.yml" in lines[0], (name, lines)
        if name != "not-yaml":
            assert "components[0]" in lines[0], (name, lines)
        for _, _, revision in component_list(data):
            assert revision not in out


def test_epm_29_unpinned_model_is_a_limit(tmp_path):
    data = valid()
    data["model"]["provider_revision"] = None
    project, code, out, err = shown(tmp_path, finish(data), models={"standard": "sonnet"})
    assert code == 0, out + err
    limits = json.loads(out)["reproducibility_limits"]
    assert [item["code"] for item in limits] == ["model-version-not-pinned"]
    assert limits[0]["tier"] == "standard" and limits[0]["model"] == "sonnet"
    code, plain, err = profile(project, "show", "lean-implement", "--version", "1")
    assert code == 0, plain + err
    assert [line for line in plain.splitlines()
            if line.strip().startswith("model-version-not-pinned:")], plain


def test_epm_30_pinned_model_shows_no_limit(tmp_path):
    _, code, out, err = shown(tmp_path, models={"standard": "example-model"})
    assert code == 0, out + err
    doc = json.loads(out)
    assert doc["reproducibility_limits"] == []
    assert doc["model"]["provider_revision"] == "example-model-2026-10-01"
    assert doc["model"]["mapped_model"] == "example-model"


def test_epm_31_inherit_tier_is_a_limit(tmp_path):
    for name, revision, expected in (
            ("pinned", "example-model-2026-10-01", ["model-follows-session"]),
            ("unpinned", None, ["model-follows-session", "model-version-not-pinned"])):
        data = valid()
        data["model"]["tier"] = "strong"
        data["model"]["provider_revision"] = revision
        _, code, out, err = shown(tmp_path / name, finish(data), models={"strong": "inherit"})
        assert code == 0, (name, out, err)
        limits = json.loads(out)["reproducibility_limits"]
        assert [item["code"] for item in limits] == expected, name
        assert "session" in limits[0]["message"]


def test_epm_32_profile_approval_is_reported_not_enforced(tmp_path):
    for state in ("pending", "approved"):
        data = valid()
        data["approval"]["state"] = state
        _, code, out, err = shown(tmp_path / state, finish(data))
        assert code == 0, (state, out, err)
        doc = json.loads(out)
        assert doc["approval"]["state"] == state and doc["owner"] == "jed72"


# --- group D: nothing governed changes ---

SLUG = "tiers"
JUSTIFY = ["--justify", "risk=r", "--justify", "familiarity=f",
           "--justify", "size=s", "--justify", "goal=g"]
ISSUE_ENV = {"COMPASS_ISSUE": SLUG}
GOVERNED_SEATS = ("assess", "define", "refine", "plan", "breakdown", "implement", "verify",
                  "review", "ship")


def assessed_project(tmp_path):
    """A project with a `compass.yml` and one issue assessed with `--write`."""
    root = make(tmp_path)
    compass_yml(root)
    task = root / ".compass" / "work" / SLUG
    task.mkdir(parents=True)
    (task / "manifest.yml").write_text(yaml.safe_dump({
        "schema_version": "3.0", "issue": SLUG, "created": "2026-10-17",
        "assessment": {"risk": "contained", "familiarity": "brownfield-mapped",
                       "size": "medium", "goal": "delivery", "labels": []}}),
        encoding="utf-8")
    code, out, err = support.run_compass(root, "approach", "evaluate", "--issue", SLUG,
                                         "--write", *JUSTIFY, env=ISSUE_ENV)
    assert code == 0, out + err
    return root


def snapshot(root, skip=("profiles", ".git")):
    """`{relative path: sha256}` of every file under `root` outside `skip`."""
    found = {}
    for path in sorted(Path(root).rglob("*")):
        relative = path.relative_to(root)
        if relative.parts[0] in skip or not path.is_file():
            continue
        found[str(relative)] = hashlib.sha256(path.read_bytes()).hexdigest()
    return found


def test_epm_33_tier_and_setting_are_referenced(tmp_path):
    data = valid()
    project = make(tmp_path)
    stored = store(project, data)
    write_registry(project, registry_for(data))
    compass_yml(project, {"standard": "sonnet"})
    before = stored.read_bytes()
    first = json.loads(profile(project, "show", "lean-implement", "--version", "1",
                               "--json")[1])
    compass_yml(project, {"standard": "opus"})
    second = json.loads(profile(project, "show", "lean-implement", "--version", "1",
                                "--json")[1])
    assert first["model"]["mapped_model"] == "sonnet"
    assert second["model"]["mapped_model"] == "opus"
    assert stored.read_bytes() == before
    assert first["digest"] == second["digest"] == data["digest"]
    text = before.decode("utf-8")
    for name in ("sonnet", "opus", "haiku", "inherit"):
        assert name not in text, name


def test_epm_34_routing_policy_key_is_refused(tmp_path):
    rows = (("model_rules", "policy-copy"), ("default_tiers", "policy-copy"),
            ("floors", "policy-copy"), ("loop_ceilings", "policy-copy"),
            ("readiness_floor", "policy-copy"), ("notes", "field-unknown"),
            ("model.name", "field-unknown"))
    for index, (key, code_name) in enumerate(rows):
        data = valid()
        if key == "model.name":
            data["model"]["name"] = "sonnet"
        else:
            data[key] = {"extra": 1}
        _, code, out, _ = lint_data(tmp_path / str(index), finish(data))
        assert code == 2, (key, out)
        lines = [line for line in reason_lines(out) if line.startswith(code_name)]
        assert len(lines) == 1 and key in lines[0], (key, out)


def test_epm_35_setting_over_ceiling_is_refused(tmp_path):
    rows = (("max_cycles", 31, "30"), ("max_minutes", 241, "240"), ("max_cost_usd", 5.01, "5"))
    for index, (setting, value, ceiling) in enumerate(rows):
        data = valid()
        data["runner_settings"][setting] = value
        _, code, out, _ = lint_data(tmp_path / str(index), finish(data))
        assert code == 2, (setting, out)
        lines = [line for line in reason_lines(out)
                 if line.startswith("runner-setting-over-ceiling")]
        assert len(lines) == 1, (setting, out)
        assert setting in lines[0] and f"is {value}," in lines[0], lines
        assert f"ceiling {ceiling} " in lines[0], lines


def test_epm_36_setting_at_ceiling_is_accepted(tmp_path):
    data = valid()
    data["runner_settings"] = {"max_cycles": 30, "max_minutes": 240, "max_cost_usd": 5}
    _, code, out, err = lint_data(tmp_path, finish(data))
    assert code == 0, out + err


def policy_project(tmp_path, ceiling, limit):
    """A project whose own routing policy limits `ceiling` to `limit`."""
    project = make(tmp_path)
    folder = project / "governance"
    folder.mkdir()
    shutil.copy(ROOT / "governance" / "guardrails.yml", folder / "guardrails.yml")
    policy = yaml.safe_load((ROOT / "governance" / "routing-policy.yml").read_text(
        encoding="utf-8"))
    rules = policy["routing_guardrails"]["loop_ceilings"]
    assert any(rule["ceiling"] == ceiling for rule in rules)
    for rule in rules:
        if rule["ceiling"] == ceiling:
            rule["limit"] = limit
    (folder / "routing-policy.yml").write_text(yaml.safe_dump(policy), encoding="utf-8")
    return project


def test_epm_44_ceilings_follow_the_policy(tmp_path):
    rows = (("run_cycles", "max_cycles", 20, 21), ("run_minutes", "max_minutes", 120, 121),
            ("run_cost_usd", "max_cost_usd", 2, 2.01))
    for index, (ceiling, setting, limit, over) in enumerate(rows):
        project = policy_project(tmp_path / str(index), ceiling, limit)
        data = valid()
        data["runner_settings"][setting] = over
        path = put(project / "work", finish(data))
        code, out, err = profile(project, "lint", str(path))
        assert code == 2, (setting, out, err)
        lines = [line for line in reason_lines(out)
                 if line.startswith("runner-setting-over-ceiling")]
        assert len(lines) == 1 and setting in lines[0], (setting, out)
        assert f"is {over}," in lines[0] and f"ceiling {limit} " in lines[0], lines


def test_epm_37_no_tier_effort_or_floor_changes(tmp_path):
    project = assessed_project(tmp_path)

    def outputs():
        runs = [("approach", "show")]
        for seat in GOVERNED_SEATS:
            runs += [("approach", "show", "--model", seat),
                     ("approach", "show", "--effort", seat)]
        assert len(runs) == 19
        return [support.run_compass(project, *argv, env=ISSUE_ENV) for argv in runs]

    recorded = outputs()
    assert all(code == 0 for code, _, _ in recorded), recorded[0]
    data = valid()
    data["model"].update(tier="fast", effort="low")
    path = put(project / "work", finish(data))
    assert profile(project, "add", str(path))[0] == 0
    write_registry(project, registry_for(data))
    assert profile(project, "show", "lean-implement", "--version", "1")[0] == 0
    assert outputs() == recorded


def test_epm_38_no_gate_approval_or_permission_changes(tmp_path):
    project = assessed_project(tmp_path)
    (project / "governance").mkdir()
    (project / "governance" / "notes.md").write_text("project notes\n", encoding="utf-8")
    data = valid()
    write_registry(project, registry_for(data))
    registry_before = (project / "profiles" / "component-registry.yml").read_bytes()
    checked = support.run_compass(project, "check", "--json", env=ISSUE_ENV)
    assert checked[1].lstrip().startswith("{"), checked
    before = snapshot(project)
    path = put(project / "work", data)
    before["work/profile.yml"] = hashlib.sha256(path.read_bytes()).hexdigest()
    assert profile(project, "lint", str(path))[0] == 0
    assert profile(project, "add", str(path))[0] == 0
    assert profile(project, "show", "lean-implement", "--version", "1")[0] == 0
    assert snapshot(project) == before
    assert support.run_compass(project, "check", "--json", env=ISSUE_ENV) == checked
    assert store_files(project) == ["lean-implement.1.yml"]
    assert sorted(p.name for p in (project / "profiles").iterdir()) == [
        "component-registry.yml", "lean-implement.1.yml"]
    assert (project / "profiles" / "component-registry.yml").read_bytes() == registry_before


STUB_CLAUDE = '''#!/usr/bin/env python3
import json, os, sys
with open(os.environ["STUB_LOG"], "a") as log:
    log.write(json.dumps([sys.argv[1:], sys.stdin.read() if not sys.stdin.isatty() else ""]) + "\\n")
print(json.dumps({"type": "result", "subtype": "success", "is_error": False,
                  "result": "done", "session_id": "s1", "total_cost_usd": 0.01}))
'''


def stub_run(tmp_path, with_store):
    """Run one stage of the issue with a stub `claude`. Returns what the stub got,
    with the project path replaced, and the issue manifest text."""
    root = tmp_path / "root"
    project = assessed_project(root)
    (project / "docs" / "compass" / "2026-10-17-tiers").mkdir(parents=True, exist_ok=True)
    if with_store:
        data = valid()
        store(project, data)
        write_registry(project, registry_for(data))
    stub = tmp_path / "bin" / "claude"
    put(stub.parent, STUB_CLAUDE, "claude")
    stub.chmod(0o755)
    log = tmp_path / "stub.log"
    code, out, err = support.run_compass(
        project, "run", SLUG, "--stage", "verify", "--stop-file", str(tmp_path / "STOP"),
        "--claude", str(stub), "--max-cycles", "1",
        env={"STUB_LOG": str(log), "COMPASS_ISSUE": SLUG})
    assert code in (0, 4), out + err
    received = log.read_text(encoding="utf-8").replace(str(project), "<project>")
    manifest = (project / ".compass" / "work" / SLUG / "manifest.yml").read_text(
        encoding="utf-8")
    return received, manifest


def test_epm_39_no_selection_and_no_experiment(tmp_path):
    with_store, manifest = stub_run(tmp_path / "with", True)
    without_store, _ = stub_run(tmp_path / "without", False)
    assert with_store and with_store == without_store
    assert "profile" not in " ".join(yaml.safe_load(manifest))
    project = make(tmp_path / "help")
    code, out, err = profile(project, "--help")
    assert code == 0, out + err
    listed = re.search(r"\{([a-z,]+)\}", out)
    assert listed and set(listed.group(1).split(",")) == {"lint", "add", "show"}
    hits = [(path, name) for path, name in verbs_and_options(root_parser())
            if "profile" in name and (path, name) != ((), "profile")]
    assert hits == [], hits


def verbs_and_options(parser, path=()):
    """Every verb and option name in the parser tree, with the verbs above it."""
    for action in parser._actions:
        for option in action.option_strings:
            yield path, option
        if isinstance(action, argparse._SubParsersAction):
            for name, child in action.choices.items():
                yield path, name
                yield from verbs_and_options(child, path + (name,))


def root_parser():
    import importlib.util
    from importlib.machinery import SourceFileLoader
    import compass_pkg  # noqa: F401  - resolves the bundled yaml
    cli = ROOT / "cli" / "compass"
    spec = importlib.util.spec_from_loader("compass_entry_profiles", SourceFileLoader(
        "compass_entry_profiles", str(cli)))
    module = importlib.util.module_from_spec(spec)
    old = sys.argv
    sys.argv = ["compass"]
    try:
        spec.loader.exec_module(module)
    finally:
        sys.argv = old
    return module.build_parser()


# --- group E: fixtures, documentation and hygiene ---

SCHEMA = ROOT / "schemas" / "execution-profile.schema.json"
OWNING_DOC = ROOT / "docs" / "execution-profiles.md"


def schema_errors(validator, data):
    return sorted(error.message for error in validator.iter_errors(data))


def walk_schema(node):
    """Every key and every text value in the schema, with the key it sits under."""
    if isinstance(node, dict):
        for key, value in node.items():
            yield key, key
            yield from walk_schema(value)
    elif isinstance(node, list):
        for value in node:
            yield from walk_schema(value)
    elif isinstance(node, str):
        yield None, node


def test_epm_40_four_fixtures(tmp_path):
    try:
        import jsonschema
    except ImportError:
        pytest.fail("jsonschema is not installed, so the schema cannot be checked. Install "
                    "it with: python3 -m pip install -r .github/requirements/self-check.txt")
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    jsonschema.Draft7Validator.check_schema(schema)
    validator = jsonschema.Draft7Validator(schema)
    for name in ("valid", "changed", "missing-component", "incompatible-component"):
        assert schema_errors(validator, load_fixture(name)) == [], name
    without_id = valid()
    del without_id["id"]
    assert schema_errors(validator, without_id) != []

    from compass_pkg import model_tiers
    names = set(model_tiers.TIERS) | set(model_tiers.EFFORTS) | {
        "run_cycles", "run_minutes", "run_cost_usd"}
    for key, text in walk_schema(schema):
        assert key not in ("enum", "maximum", "exclusiveMaximum"), key
        assert text not in names, text

    project = make(tmp_path / "valid", "valid")
    store(project, load_fixture("valid"))
    assert profile(project, "show", "lean-implement", "--version", "1")[0] == 0

    project = make(tmp_path / "changed", "changed")
    v1 = yaml.safe_load((project / "profiles" / "lean-implement.1.yml").read_text(
        encoding="utf-8"))
    code, out, err = profile(project, "add", str(FIXTURES / "changed" / "profile.yml"))
    assert code == 0, out + err
    v2 = yaml.safe_load((project / "profiles" / "lean-implement.2.yml").read_text(
        encoding="utf-8"))
    assert v1["digest"] != v2["digest"]

    for name, expected in (("missing-component", "component-missing"),
                           ("incompatible-component", "component-incompatible")):
        project = make(tmp_path / name, name)
        store(project, load_fixture(name))
        code, out, err = profile(project, "show", "lean-implement", "--version", "1")
        assert code == 2 and codes(out) == [expected], (name, out, err)


def doc_codes(text):
    """The reason codes the owning document lists: the first cell of each table row."""
    return re.findall(r"^\| `([a-z][a-z-]+)` \|", text, re.M)


def test_epm_41_owning_document_matches_the_code():
    from compass_pkg import execution_profile as ep
    text = OWNING_DOC.read_text(encoding="utf-8")
    listed = doc_codes(text)
    assert sorted(listed) == sorted(ep.ALL_CODES), (
        sorted(set(listed) ^ set(ep.ALL_CODES)), [c for c in listed if listed.count(c) > 1])
    for verb in ("profile lint", "profile add", "profile show"):
        assert f"compass {verb}" in text, verb
    docs_readme = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
    owning = docs_readme.split("## Owning docs", 1)[1]
    rows = [line for line in owning.splitlines()
            if line.startswith("|") and "docs/execution-profiles.md" in line]
    assert len(rows) == 1 and "execution_profile_cmd.py" in rows[0], rows
    assert "(execution-profiles.md)" in docs_readme
    assert "execution-profile.schema.json" in (ROOT / "schemas" / "README.md").read_text(
        encoding="utf-8")


# The private record is never named in a file this change adds or edits. Each needle is
# assembled from parts, so this file does not hold one.
NEEDLES = {
    "repository name": re.compile("compass" + "-delivery-" + "record"),
    "link": re.compile(r"github\.com/" + "ayeo-io/" + "compass-delivery-" + "record"),
    "document id": re.compile(r"\b" + "PR" + "D" + r"[- ]?[0-9]"),
    "requirement id": re.compile(r"\b" + "F" + "R" + r"-[0-9]"),
}
SAMPLES = {"repository name": "compass" + "-delivery-" + "record",
           "link": "https://github.com/" + "ayeo-io/" + "compass-delivery-" + "record/issues/1",
           "document id": "PR" + "D" + " 7", "requirement id": "F" + "R" + "-4"}
ADDED = ("cli/compass_pkg/execution_profile*.py", "tests/fixtures/execution-profiles/**/*",
         "schemas/execution-profile.schema.json", "docs/execution-profiles.md",
         "tests/test_execution_profiles.py", "architecture/decisions/ADR-076-*.md")
EDITED = ("cli/compass", "cli/compass_pkg/verb_help.py", "docs/cli.md",
          "tests/fixtures/cli-surface-baseline.json", "tests/test_bdd_extract.py",
          "tests/test_phase2_invariants.py", "tests/test_governance_drift_noop.py",
          "tests/cross_cutting/test_stream_d_invariants.py",
          "tests/test_fresh_eyes_verify_sweeps.py", "tests/test_faster_suite.py",
          "tests/test_writing_style.py", "docs/README.md", "schemas/README.md",
          "governance/terminology.yml",
          "docs/glossary.md", "architecture/decisions/README.md")


def needle_hits(paths):
    hits = []
    for path in paths:
        text = Path(path).read_text(encoding="utf-8")
        hits += [(str(path), name) for name, needle in NEEDLES.items() if needle.search(text)]
    return hits


def test_epm_42_no_private_record_text(tmp_path):
    paths = sorted({p for pattern in ADDED for p in ROOT.glob(pattern) if p.is_file()})
    paths += [ROOT / name for name in EDITED]
    assert len(paths) > len(EDITED) + 8, paths
    assert needle_hits(paths) == []
    for name, sample in SAMPLES.items():
        planted = tmp_path / "planted.txt"
        planted.write_text(f"a line\n{sample}\nanother line\n", encoding="utf-8")
        # A link holds the repository name too, so both needles may match it.
        assert (str(planted), name) in needle_hits([planted]), name
    own = Path(__file__).read_text(encoding="utf-8")
    for sample in SAMPLES.values():
        assert sample not in own, "the test source holds a needle in one piece"


@pytest.mark.serial
def test_epm_43_large_profile_is_shown_in_5_seconds(tmp_path):
    import time
    data = valid()
    kinds = (("skills", "skill"), ("prompt_fragments", "prompt_fragment"),
             ("tool_guidance", "tool_guidance"))
    entries = []
    for name, kind in kinds:
        data["components"][name] = []
    for n in range(100):
        name, kind = kinds[n % 3]
        ref = {"id": f"{kind.replace('_', '-')}-{n}",
               "revision": "sha256:" + hashlib.sha256(str(n).encode()).hexdigest()}
        data["components"][name].append(ref)
    for name, kind in kinds:
        entries += [entry_for(kind, ref["id"], ref["revision"])
                    for ref in data["components"][name]]
    for n in range(900):
        entries.append(entry_for("skill", f"other-{n}", "sha256:" + hashlib.sha256(
            f"other{n}".encode()).hexdigest()))
    assert len(entries) == 1000
    data = finish(data)
    project = make(tmp_path)
    store(project, data)
    write_registry(project, entries)
    started = time.monotonic()
    code, out, err = profile(project, "show", "lean-implement", "--version", "1", "--json")
    elapsed = time.monotonic() - started
    assert code == 0, out + err
    assert len(json.loads(out)["components"]) == 100
    assert elapsed < 5, elapsed


# --- review round 1: edge cases of formats, the runner list, file names and links ---


def test_epm_4_trailing_newline_is_malformed(tmp_path):
    rows = (("id", "lean-x\n", "field-malformed"),
            ("revision", "sha256:" + "ab" * 32 + "\n", "revision-not-exact"),
            ("runner", "7.0.0\n", "field-malformed"))
    for index, (kind, value, reason) in enumerate(rows):
        data = valid()
        if kind == "id":
            data["id"] = value
        elif kind == "revision":
            data["components"]["skills"][0]["revision"] = value
        else:
            data["runner_versions"][0] = value
        project = make(tmp_path / str(index))
        path = put(project / "work", finish(data))
        for verb in ("lint", "add"):
            code, out, err = profile(project, verb, str(path))
            assert code == 2, (kind, verb, out, err)
            assert codes(out) == [reason], (kind, verb, out)
        assert store_files(project) == [], kind
        folder = project / "profiles"
        assert not folder.exists() or not [p for p in folder.iterdir() if "\n" in p.name]
    # The same formats in the registry and in the id argument of show.
    project = make(tmp_path / "registry")
    data = valid()
    store(project, data)
    entries = registry_for(data)
    entries[0]["revision"] += "\n"
    entries[1]["runner_versions"] = ["7.0.0\n"]
    write_registry(project, entries)
    code, out, err = profile(project, "show", "lean-implement", "--version", "1")
    assert code == 2, out + err
    assert codes(out) == ["field-malformed", "field-malformed"], out
    code, out, err = profile(project, "show", "lean-implement\n", "--version", "1")
    assert code == 2 and codes(out) == ["profile-missing"], out + err


def test_epm_47_empty_runner_versions_are_refused(tmp_path):
    data = valid()
    data["runner_versions"] = []
    project = make(tmp_path)
    path = put(project / "work", finish(data))
    for verb in ("lint", "add"):
        code, out, err = profile(project, verb, str(path))
        assert code == 2, (verb, out, err)
        lines = reason_lines(out)
        assert len(lines) == 1 and lines[0].startswith("field-malformed"), out
        assert "runner_versions" in lines[0], out
        assert "it must list at least one runner version" in lines[0], out
    assert store_files(project) == []


def test_epm_18_file_name_that_differs_from_content_is_refused(tmp_path):
    project = make(tmp_path, "valid")
    one = valid()
    store(project, one, "lean-implement.2.yml")
    store(project, one, "other-profile.1.yml")
    write_registry(project, registry_for(one))
    code, out, err = profile(project, "show", "lean-implement", "--version", "2")
    assert code == 2, out + err
    assert codes(out) == ["field-malformed"], out
    assert "the file name says version 2 but the file holds version 1" in out, out
    code, out, err = profile(project, "show", "other-profile", "--version", "1")
    assert code == 2, out + err
    assert codes(out) == ["field-malformed"], out
    assert "the file name says other-profile but the file holds lean-implement" in out, out
    for ref in one["components"]["skills"]:
        assert ref["revision"] not in out


def test_epm_8_symlink_in_profiles_is_refused(tmp_path):
    project = make(tmp_path)
    data = valid()
    real = put(project / "work", data, "real.yml")
    (project / "profiles").mkdir()
    (project / "profiles" / "lean-implement.1.yml").symlink_to(real)
    code, out, err = profile(project, "show", "lean-implement", "--version", "1")
    assert code == 2, out + err
    assert codes(out) == ["file-unreadable"], out
    assert "symbolic link" in out, out
    no_trace(out, err)
    other = make(tmp_path / "registry")
    store(other, data)
    target = write_registry(other, registry_for(data))
    moved = target.parent.parent / "work" / "registry.yml"
    moved.parent.mkdir()
    target.rename(moved)
    target.symlink_to(moved)
    code, out, err = profile(other, "show", "lean-implement", "--version", "1")
    assert code == 2, out + err
    assert codes(out) == ["file-unreadable"], out
    assert "symbolic link" in out, out
    # A file that lint is given by name is read as before, even through a link.
    code, out, err = profile(other, "lint", str(real))
    assert code == 0, out + err
