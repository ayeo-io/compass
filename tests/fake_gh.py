#!/usr/bin/env python3
"""A stand-in for the `gh` command, so the label sync tests never reach the network.

Not a test module: pytest does not collect it. The test fixture writes a
`gh` wrapper that runs this file with the same interpreter.

State lives in the directory named by FAKE_GH_DIR:

- `calls.jsonl`: one JSON list per call, the argument list `gh` received;
- `state.json`: `repo_labels` (the labels the repository has) and `issues`
  (the labels on each issue, keyed `owner/repo#number`).

FAKE_GH_MODE makes every call fail: `unauth` as `gh` does when it is not
logged in, `down` as it does when GitHub cannot be reached.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def _flag_values(argv, flag):
    return [argv[i + 1] for i, word in enumerate(argv[:-1]) if word == flag]


def main(argv):
    base = Path(os.environ["FAKE_GH_DIR"])
    with open(base / "calls.jsonl", "a", encoding="utf-8") as log:
        log.write(json.dumps(argv) + "\n")
    mode = os.environ.get("FAKE_GH_MODE", "")
    if mode == "unauth":
        sys.stderr.write("To get started with GitHub CLI, please run:  gh auth login\n")
        return 4
    if mode == "down":
        sys.stderr.write("error connecting to api.github.com\n")
        return 1
    state_path = base / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    repo = (_flag_values(argv, "--repo") or [""])[0]
    if argv[:2] == ["label", "list"]:
        print(json.dumps([{"name": name} for name in state["repo_labels"]]))
        return 0
    # GitHub treats label names case-insensitively, so this does too.
    if argv[:2] == ["label", "create"]:
        name = argv[2]
        if name.casefold() in {n.casefold() for n in state["repo_labels"]}:
            sys.stderr.write(f'label with name "{name}" already exists\n')
            return 1
        state["repo_labels"].append(name)
        state_path.write_text(json.dumps(state), encoding="utf-8")
        return 0
    if argv[:2] in (["issue", "view"], ["issue", "edit"]):
        key = f"{repo}#{argv[2]}"
        labels = state["issues"].setdefault(key, [])
        if argv[1] == "view":
            print(json.dumps({"labels": [{"name": name} for name in labels]}))
            return 0
        for name in _flag_values(argv, "--add-label"):
            if name.casefold() not in {n.casefold() for n in labels}:
                labels.append(name)
        for name in _flag_values(argv, "--remove-label"):
            labels[:] = [n for n in labels if n.casefold() != name.casefold()]
        state_path.write_text(json.dumps(state), encoding="utf-8")
        return 0
    sys.stderr.write("fake gh: unknown command: " + " ".join(argv) + "\n")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
