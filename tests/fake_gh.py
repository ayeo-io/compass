#!/usr/bin/env python3
"""A stand-in for the `gh` command, so the GitHub sync tests never reach the network.

Not a test module: pytest does not collect it. The test fixture writes a
`gh` wrapper that runs this file with the same interpreter.

State lives in the directory named by FAKE_GH_DIR:

- `calls.jsonl`: one JSON list per call, the argument list `gh` received;
- `stdin.jsonl`: one JSON object per `api` call that read standard input,
  `{"argv": [...], "stdin": "..."}`, so a test can see the text that was sent;
- `state.json`: `repo_labels` (the labels the repository has), `issues`
  (the labels on each issue, keyed `owner/repo#number`), and for the issue
  page `comments` (each issue's comments, `[{"id", "body"}]`), `bodies` and
  `titles` (keyed the same way) and `next_id`.

FAKE_GH_MODE makes every call fail: `unauth` as `gh` does when it is not
logged in, `down` as it does when GitHub cannot be reached.

FAKE_GH_FAIL makes one kind of call fail as `down` does: `api` fails every
`gh api` call (the issue page), `labels` fails every other call (the labels).
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

_COMMENTS = re.compile(r"repos/([^/]+/[^/]+)/issues/([0-9]+)/comments")
_COMMENT = re.compile(r"repos/([^/]+/[^/]+)/issues/comments/([0-9]+)")
_ISSUE = re.compile(r"repos/([^/]+/[^/]+)/issues/([0-9]+)")


def _flag_values(argv, flag):
    return [argv[i + 1] for i, word in enumerate(argv[:-1]) if word == flag]


def _down():
    sys.stderr.write("error connecting to api.github.com\n")
    return 1


def _save(path, state):
    path.write_text(json.dumps(state), encoding="utf-8")


def _api(argv, base, state, state_path):
    """The REST calls the issue page makes: list, create and edit comments, and
    read and edit an issue."""
    path = argv[1] if len(argv) > 1 else ""
    method = (_flag_values(argv, "--method") or ["GET"])[0]
    sent = None
    if "--input" in argv:
        text = sys.stdin.read()
        with open(base / "stdin.jsonl", "a", encoding="utf-8") as log:
            log.write(json.dumps({"argv": argv, "stdin": text}) + "\n")
        sent = json.loads(text)
    comments = state.setdefault("comments", {})
    found = _COMMENTS.fullmatch(path)
    if found:
        key = f"{found.group(1)}#{found.group(2)}"
        if method == "GET":
            # `--paginate --slurp` gives a list of pages, each a list.
            print(json.dumps([comments.get(key, [])]))
            return 0
        if method == "POST":
            state["next_id"] = state.get("next_id", 1000) + 1
            made = {"id": state["next_id"], "body": sent["body"]}
            comments.setdefault(key, []).append(made)
            _save(state_path, state)
            print(json.dumps(made))
            return 0
    found = _COMMENT.fullmatch(path)
    if found and method == "PATCH":
        wanted = int(found.group(2))
        for key, items in comments.items():
            if key.split("#")[0] != found.group(1):
                continue
            for item in items:
                if item["id"] == wanted:
                    item["body"] = sent["body"]
                    _save(state_path, state)
                    print(json.dumps(item))
                    return 0
        sys.stderr.write("gh: Not Found (HTTP 404)\n")
        return 1
    found = _ISSUE.fullmatch(path)
    if found:
        key = f"{found.group(1)}#{found.group(2)}"
        bodies, titles = state.setdefault("bodies", {}), state.setdefault("titles", {})
        if method == "PATCH":
            if "body" in sent:
                bodies[key] = sent["body"]
            if "title" in sent:
                titles[key] = sent["title"]
            _save(state_path, state)
        print(json.dumps({"number": int(found.group(2)), "title": titles.get(key, "An issue"),
                          "body": bodies.get(key, "")}))
        return 0
    sys.stderr.write("fake gh: unknown api call: " + " ".join(argv) + "\n")
    return 2


def main(argv):
    base = Path(os.environ["FAKE_GH_DIR"])
    with open(base / "calls.jsonl", "a", encoding="utf-8") as log:
        log.write(json.dumps(argv) + "\n")
    mode = os.environ.get("FAKE_GH_MODE", "")
    if mode == "unauth":
        sys.stderr.write("To get started with GitHub CLI, please run:  gh auth login\n")
        return 4
    if mode == "down":
        return _down()
    fail = os.environ.get("FAKE_GH_FAIL", "")
    is_api = argv[:1] == ["api"]
    if (fail == "api" and is_api) or (fail == "labels" and not is_api):
        return _down()
    state_path = base / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    if is_api:
        return _api(argv, base, state, state_path)
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
        _save(state_path, state)
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
        _save(state_path, state)
        return 0
    sys.stderr.write("fake gh: unknown command: " + " ".join(argv) + "\n")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
