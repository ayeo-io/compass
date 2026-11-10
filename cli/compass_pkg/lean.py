# compass_pkg.lean - the record keeping `compass quick-fix finish` does itself
"""The lean path (experiment branch `exp-lean`): Compass keeps the record.

A measurement of Compass 9.0.0 showed an agent making about 100 `compass`
calls on a medium change, most of them record keeping: `tdd-red`,
`tdd-green`, `scenario add`, `changed-file add`, `evidence add`, `gate pass`
and waivers. Each call resends the whole context. On this branch the agent
writes tests and code freely and `compass quick-fix finish` writes the
record in one call. This module holds the parts of that call:

- `sync_scenarios` copies the scenarios of `acceptance-criteria.md` into the
  manifest, so no `compass scenario add` is needed;
- `changed_paths` reads the changed files from git (the diff against the
  commit the issue started from, plus untracked files), so no
  `compass changed-file add` is needed;
- `is_test_path` says which changed files are tests or test support;
- `prove_red` builds a copy of the base commit in a temporary directory,
  lays the changed test files over it, runs the test command there and
  needs it to fail. That failure is the red record: the tests fail without
  the change;
- `request_owed_approvals` writes the request for the `G5` sign-off and the
  ship approval when each is owed and not yet asked for.

The red is proved by `finish`, after the code exists, so its record says
`proved_on: base-copy` and names the base commit. It shows the tests fail
without the change. It does not show the order the files were written in.
"""
# DEPENDENCY: standard library; compass_pkg.core, pytest_report, start_state and
# tdd; inside functions approval_requests, approvals, checks, scenario_freeze and
# ship_approval.
from __future__ import annotations

import fnmatch
import json
import os
import re
import shutil
import subprocess
import tempfile
import time

from compass_pkg import pytest_report
from compass_pkg.core import CompassError, docs_dir, load_manifest, now_iso, save_manifest
from compass_pkg.start_state import (_is_generated, _is_issue_state, _record_path,
                                     _tracked_paths)

#: The manifest key that holds the commit the issue started from.
BASE_KEY = "base_commit"
#: The manifest key that holds the commit message `finish` was given.
MESSAGE_KEY = "commit_message"
#: The value of `proved_on` on a red record that `finish` proved itself.
BASE_COPY = "base-copy"

#: Files a test run leaves behind. They are never part of the change.
_RUN_OUTPUT = (".coverage", "coverage.xml", "coverage.json", ".coverage.*", "junit.xml")
_RUN_OUTPUT_DIRS = ("htmlcov", ".hypothesis", "node_modules", ".venv", "venv")

#: Folder names that hold tests or test support, in any language.
_TEST_DIRS = frozenset({"tests", "test", "__tests__", "spec", "specs", "testing",
                        "testdata", "fixtures", "e2e", "acceptance"})
#: File name patterns of a test file, in any language.
_TEST_NAMES = ("test_*", "*_test.*", "*.test.*", "*.spec.*", "*_spec.*", "conftest.py",
               "*Test.java", "*Tests.java", "*Test.kt", "*Tests.cs", "*Test.php")

#: Folders of installed dependencies. The base copy links to them, because the
#: base commit does not hold them and the tests cannot run without them.
_DEPENDENCY_DIRS = ("node_modules", ".venv", "venv")

_HEADING = re.compile(r"^###\s+Scenario(?: Outline| Template)?:\s*(?P<title>.+?)\s*$")
_TRACE = re.compile(r"<!--\s*traceability id:\s*(?P<id>[A-Z][A-Z0-9]*-[A-Za-z0-9_]+)\b"
                    r"(?:.*?serves:\s*(?P<intent>[A-Z][A-Z0-9]*-[A-Za-z0-9_]+))?.*?-->")


def is_test_path(path):
    """True when `path` is a test file or a test support file: it sits under a
    test folder, or its name matches a common test file pattern."""
    parts = path.replace("\\", "/").split("/")
    if any(p.lower() in _TEST_DIRS for p in parts[:-1]):
        return True
    return any(fnmatch.fnmatchcase(parts[-1], pattern) for pattern in _TEST_NAMES)


def _git(args, cwd, text=True):
    return subprocess.run(["git"] + list(args), cwd=cwd, capture_output=True, text=text)


def head_commit(root):
    """The `HEAD` commit of the repository at `root`, or None with no commit."""
    done = _git(["rev-parse", "--verify", "-q", "HEAD"], root)
    return done.stdout.strip() or None if done.returncode == 0 else None


def base_commit(task, root, slug):
    """The commit the issue started from: the manifest's `base_commit`, else the
    `head_at_start` of the start record, else `HEAD`."""
    held = task.get(BASE_KEY)
    if isinstance(held, str) and held:
        return held
    try:
        with open(_record_path(root, slug), encoding="utf-8") as fh:
            head = json.load(fh).get("head_at_start")
        if head:
            return head
    except (OSError, ValueError, AttributeError, subprocess.CalledProcessError):
        pass
    return head_commit(root)


def _run_output(path):
    parts = path.split("/")
    return (any(p in _RUN_OUTPUT_DIRS for p in parts[:-1])
            or any(fnmatch.fnmatchcase(parts[-1], pattern) for pattern in _RUN_OUTPUT))


def _before_start(root, slug):
    """`(paths, folders)` that were already changed or untracked at `start`."""
    try:
        with open(_record_path(root, slug), encoding="utf-8") as fh:
            data = json.load(fh)
        return (set(data.get("changed_before_start") or ()),
                set(data.get("local_dirs_before_start") or ()))
    except (OSError, ValueError, AttributeError, subprocess.CalledProcessError):
        return set(), set()


def changed_paths(root, base, slug, doc_prefix, keep=()):
    """`(code, documents, left_out)`: the paths the change holds, read from git.

    The change is every path that differs between the base commit and the
    working tree, plus every untracked path git does not ignore. The issue's
    own state, caches and the files a test run leaves are not the change. A
    path that was already changed or untracked when the issue started is left
    out and named, unless `keep` (the paths traced by hand) holds it.
    `documents` are the paths under the issue's documents folder."""
    names = set()
    if base:
        diff = _git(["diff", "--name-only", "-z", "--no-renames", "--relative", base, "--"],
                    root)
        if diff.returncode != 0:
            raise CompassError(f"compass quick-fix finish: git cannot read the base commit "
                               f"{base[:12]}: {diff.stderr.strip()[:200]}")
        names.update(p for p in diff.stdout.split("\0") if p)
    other = _git(["ls-files", "-z", "--others", "--exclude-standard"], root)
    names.update(p for p in other.stdout.split("\0") if p)
    tracked = _tracked_paths(root)
    before_paths, before_dirs = _before_start(root, slug)
    code, documents, left_out = [], [], []
    for path in sorted(names):
        if path.startswith(doc_prefix):
            documents.append(path)
        elif _is_issue_state(path, tracked) or path.startswith(".compass/") \
                or _is_generated(path) or _run_output(path):
            continue
        elif path not in keep and (path in before_paths or any(
                path.startswith(folder) for folder in before_dirs)):
            left_out.append(path)
        else:
            code.append(path)
    return code, documents, left_out


def sync_scenarios(task, spec_path):
    """Add to the manifest each scenario of the spec it does not hold yet, and
    return the ids added. A scenario is a `### Scenario: <title>` heading with
    a `<!-- traceability id: <ID> -->` line under it, as `compass quick-fix
    start` writes the first one."""
    try:
        with open(spec_path, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    except OSError:
        return []
    scenarios = task.setdefault("scenarios", [])
    known = {s.get("id") for s in scenarios if isinstance(s, dict)}
    intents = [s.get("intent") for s in scenarios if isinstance(s, dict) and s.get("intent")]
    added, title, fenced = [], None, False
    for line in lines:
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if fenced:
            continue
        heading = _HEADING.match(line)
        if heading:
            title = heading["title"]
            continue
        trace = _TRACE.search(line)
        if trace and trace["id"] not in known:
            scenarios.append({"id": trace["id"], "title": title or trace["id"],
                              "intent": trace["intent"] or (intents[0] if intents else "INT-1"),
                              "tests": []})
            known.add(trace["id"])
            added.append(trace["id"])
        if trace:
            title = None
    return added


def record_change(task_dir, root, code, documents, tests):
    """Write the change into the manifest: each changed path traced to every
    scenario, and the changed test files as the tests of each scenario that
    declares no test file that exists. Returns the manifest as saved."""
    task, path = load_manifest(task_dir)
    ids = [s["id"] for s in task.get("scenarios") or [] if isinstance(s, dict) and s.get("id")]
    on_disk = [p for p in code + documents if os.path.lexists(os.path.join(root, p))]
    task["changed_files"] = [{"path": p, "scenarios": list(ids)} for p in on_disk]
    for scenario in task.get("scenarios") or []:
        if not isinstance(scenario, dict):
            continue
        # A declared test stays while its file is part of the change. A test
        # file the change does not touch is the same on the base commit, so it
        # shows nothing about the change.
        declared = [t for t in scenario.get("tests") or [] if isinstance(t, str)
                    and (t.split("::", 1)[0] in tests or not tests)
                    and os.path.isfile(os.path.join(root, t.split("::", 1)[0]))]
        files = {t.split("::", 1)[0] for t in declared}
        scenario["tests"] = declared + [t for t in tests if t not in files]
    save_manifest(task, path)
    return task


def _build_base_copy(root, base, tests, into):
    """Write the base commit's files under `into`, then lay the change's test
    files over them. A test file the change deleted is deleted there too."""
    top = _git(["rev-parse", "--show-toplevel"], root).stdout.strip() or root
    if base:
        archive = subprocess.run(["git", "archive", "--format=tar", base], cwd=top,
                                 capture_output=True)
        if archive.returncode != 0:
            raise CompassError(f"compass quick-fix finish: git cannot read the base commit "
                               f"{base[:12]}, so the red cannot be proved.")
        subprocess.run(["tar", "-x", "-C", into], input=archive.stdout, check=True)
    copy_root = os.path.join(into, os.path.relpath(os.path.realpath(root),
                                                   os.path.realpath(top)))
    os.makedirs(copy_root, exist_ok=True)
    for rel in tests:
        source, target = os.path.join(root, rel), os.path.join(copy_root, rel)
        if os.path.isfile(source):
            os.makedirs(os.path.dirname(target), exist_ok=True)
            shutil.copy2(source, target)
        elif os.path.lexists(target):
            os.remove(target)
    for name in _DEPENDENCY_DIRS:
        source, target = os.path.join(root, name), os.path.join(copy_root, name)
        if os.path.isdir(source) and not os.path.lexists(target):
            os.symlink(source, target)
    return copy_root


def _is_pytest(command):
    from compass_pkg.tdd import _is_pytest_command
    return _is_pytest_command(command)


def prove_red(root, base, tests, command, cwd, declared=()):
    """Run `command` on a copy of the base commit with the change's test files
    laid over it, and return `(exit code, output, red kind)`.

    Raises `CompassError`, in one line, when the run is not a red: the tests
    pass without the change, or the command did not run a test. `declared` are
    the test files the scenarios declare, for a change with no test file of its
    own. `cwd` is the
    folder the command was given in; the run starts in the same folder of the
    copy. The copy is removed afterwards."""
    from compass_pkg.tdd import _NO_TEST_RAN_EXITS, _run_test
    # With no changed test file, a test the scenarios already declare can
    # still fail on the base commit: a failing test that was there first.
    if not tests and not declared:
        raise CompassError(
            "compass quick-fix finish: the change holds no test file, so nothing shows the "
            "tests fail without it. Add or change a test; or, for a test that failed "
            "before the change, run compass scenario tests set <id> --test <path>.")
    holder = tempfile.mkdtemp(prefix="compass-base-")
    env, report, ours, before = pytest_report.with_report(command)
    try:
        copy_root = _build_base_copy(root, base, tests, holder)
        run_in = os.path.join(copy_root, os.path.relpath(os.path.realpath(cwd),
                                                         os.path.realpath(root)))
        if not os.path.isdir(run_in):
            run_in = copy_root
        prior = os.getcwd()
        os.chdir(run_in)
        try:
            # The copy must import its own files, not the working tree's.
            code, out, _warnings = _run_test(
                command, dict(env or {}, PYTHONDONTWRITEBYTECODE="1"))
        finally:
            os.chdir(prior)
        out = out.replace(os.path.realpath(holder), "<base copy>").replace(holder, "<base copy>")
        if code == 0:
            raise CompassError(
                "compass quick-fix finish: the tests pass on the base commit without the "
                "change, so they prove nothing. Add a test that fails without the change.")
        kind, why = "exit-code", None
        if pytest_report.written(report, before):
            kind, _heading, why = pytest_report.judge(report, code, root, _NO_TEST_RAN_EXITS)
        elif _is_pytest(command) and code in _NO_TEST_RAN_EXITS:
            why = _NO_TEST_RAN_EXITS[code]
        elif code in (126, 127):
            why = f"the command could not start (exit {code})"
        if why:
            raise CompassError(
                f"compass quick-fix finish: on the base commit the test command ran no "
                f"failing test: {why}. Fix the command or the test, then run finish again.")
        return code, out, kind
    finally:
        shutil.rmtree(holder, ignore_errors=True)
        if ours:
            try:
                os.remove(report)
            except OSError:
                pass


def write_reds(task_dir, scenario_ids, command, code, out, kind, base, tests, ids):
    """Write one red record per scenario from the base-copy run, as `compass
    tdd-red` writes one, and return the time on the records. The digests are
    those of the test files that ran: the same files as in the working tree."""
    from compass_pkg import scenario_freeze
    from compass_pkg.red_first import record_stem
    from compass_pkg.tdd import _write_evidence
    task, task_path = load_manifest(task_dir)
    named = set(tests) | set(ids.get("test_files") or ())
    sums = {p: d for p, d in (ids.get("file_sha256") or {}).items() if p in named}
    stamp = now_iso()
    payload = {
        "command": " ".join(command), "argv": list(command), "loop": "inner",
        "exit_code": code, "passed": False, "timestamp": stamp,
        "log_excerpt": "\n".join(out.splitlines()[-25:]), "_full_log": out,
        "red_kind": kind, "proved_on": BASE_COPY, "base_commit": base,
        "file_sha256": sums, "test_files": sorted(sums),
    }
    payload.update(scenario_freeze.red_payload(task, task_dir))
    paths = [_write_evidence(task_dir, record_stem("red", sid, "inner"),
                             dict(payload, scenario=sid)) for sid in scenario_ids]
    # The scenarios are frozen at the red that stands now, not at one a later
    # run of finish replaced.
    task, task_path = load_manifest(task_dir)
    if task.pop(scenario_freeze.KEY, None) is not None:
        save_manifest(task, task_path)
    scenario_freeze.freeze(task_dir, paths[0])
    return stamp


def wait_past(stamp):
    """Wait until the clock shows a later second than `stamp`. A record's time
    has one-second resolution, and the green must be timed after the red."""
    while now_iso() <= stamp:
        time.sleep(0.05)


def records_current(task_dir, scenario_ids, command, ids):
    """True when every scenario holds a red that `finish` proved and a green,
    both made by this command on the files as they are now. Then a second
    `finish` writes nothing new."""
    from compass_pkg.red_first import load_record, record_stem
    wanted = ids.get("file_sha256")
    if not isinstance(wanted, dict) or not ids.get("tree_id"):
        return False
    tests = {p: d for p, d in wanted.items() if p in set(ids.get("test_files") or ())}
    for sid in scenario_ids:
        red = load_record(os.path.join(task_dir, "evidence",
                                       record_stem("red", sid, "inner") + ".json"))
        green = load_record(os.path.join(task_dir, "evidence",
                                         record_stem("green", sid, "inner") + ".json"))
        if red.get("proved_on") != BASE_COPY or red.get("file_sha256") != tests \
                or red.get("argv") != list(command):
            return False
        if green.get("passed") is not True or green.get("file_sha256") != wanted \
                or green.get("tree_id") != ids["tree_id"]:
            return False
    return True


def drop_greens(task_dir, scenario_ids):
    """Remove the green record files of the scenarios, so the next green starts
    its `first_timestamp` again, after the red that replaces the old one."""
    from compass_pkg.red_first import record_stem
    for sid in scenario_ids:
        for loop in ("inner", "outer"):
            stem = os.path.join(task_dir, "evidence", record_stem("green", sid, loop))
            for ending in (".json", ".log"):
                try:
                    os.remove(stem + ending)
                except OSError:
                    pass


def specify_owed(task, task_dir):
    """The one-line refusal when the scenarios owe a person's approval and have
    none, else None. It names the pending request when one is written."""
    from compass_pkg import approval_requests, scenario_freeze
    if not scenario_freeze.owes_signoff(task) or scenario_freeze.signed_off(task):
        return None
    for request in approval_requests.pending(task_dir):
        if request.get("form") == "checkpoint" and request.get("value") == "specify":
            return (f"stop: the scenarios wait for the person's approval. Ask them to type "
                    f"/compass:approve {request.get('number')}")
    return ("write the scenarios in acceptance-criteria.md, then compass evidence request "
            "--checkpoint specify, then stop for /compass:approve")


def request_owed_approvals(task_dir):
    """Write the request for the `G5` sign-off and for the ship approval when
    each is owed, not on record and not already asked for. Returns
    `[(number, what)]` for every request that is pending afterwards."""
    from compass_pkg import approval_records, approval_requests, approvals, ship_approval
    from compass_pkg.checks import _check_human_approval
    task, _ = load_manifest(task_dir)
    owed = task.get("evidence_required") or []
    wanted = []
    if "human-approval" in owed and _check_human_approval(task, task_dir)[0] is not True:
        wanted.append(("guardrail", "G5", "the `G5` sign-off"))
    if ship_approval.owed(task) and \
            ship_approval._check_ship_approval_present(task, task_dir)[0] is not True:
        wanted.append(("ship", None, "the ship approval"))
    waiting = []
    slug = os.path.basename(os.path.normpath(task_dir))
    labels = ", ".join((task.get("assessment") or {}).get("labels") or [])
    subject = str(task.get(MESSAGE_KEY) or "").splitlines()[:1]
    # A `G5` record says for what the person approved.
    scopes = {"guardrail": (f"the change of issue {slug}, labeled {labels}"
                            + (f": {subject[0]}" if subject else ""))[:300]}
    with approvals.lock(task_dir):
        for form, value, what in wanted:
            held = next((r for r in approval_requests.pending(task_dir)
                         if r.get("form") == form and r.get("value") == value), None)
            if held is None:
                scope = scopes.get(form, "")
                answer = approvals.Answer(form, value, approval_records.APPROVED, None, "",
                                          scope)
                refused = approvals.refusal(task_dir, answer)
                if refused:
                    raise CompassError(f"compass quick-fix finish: the request for {what} "
                                       f"was refused: {refused}")
                held = approval_requests.write(task_dir, form, value, scope)
            waiting.append((held.get("number"), what))
    return waiting


def landing_refusal(task_dir):
    """Why `compass ship-commit` must not land the issue, in a few lines, or
    None: `compass check` fails. On the lean path `finish` lets the `G5`
    sign-off wait for the person, so the landing is where it is enforced."""
    from compass_pkg.check_cmd import cmd_check
    from compass_pkg.quick_fix_cmd import _check_failures, _quiet_run
    slug = os.path.basename(os.path.normpath(task_dir))
    out, code = _quiet_run(cmd_check, mode="summary", task=slug)
    if code == 0:
        return None
    return ("compass ship-commit: nothing was committed - `compass check` fails:\n  "
            + "\n  ".join(_check_failures(out))
            + "\nA person's approval is given with /compass:approve; for anything else, "
            "fix it and run compass quick-fix finish again.")


def traced_paths(task, root):
    """The paths of the change the manifest holds that git would commit: each
    `changed_files` path that is changed or untracked now."""
    out = []
    for entry in task.get("changed_files") or []:
        path = entry.get("path") if isinstance(entry, dict) else None
        if not isinstance(path, str) or not path:
            continue
        if _git(["status", "--porcelain", "--", path], root).stdout.strip():
            out.append(path)
    return out


def spec_of(task_dir):
    """The issue's `acceptance-criteria.md`, as an absolute path."""
    from compass_pkg.spec_location import spec_path
    return spec_path(task_dir)


def doc_prefix(task_dir):
    return docs_dir(task_dir) + "/"


# --- round two: one issue per request, one call per round ------------------------------------

#: The line that ends a hand-off after a commit. It says what the session need
#: not run, because measured sessions ran `git log`, `git show`, `git status`,
#: `compass status` and the tests again after each commit.
DONE = ("done: nothing more to run for this issue, before or after the merge. Do not "
        "re-check the commit or push it unless the person asks.")

#: Patterns of test-run output, written to the repository's own
#: `.git/info/exclude`, so `git status` does not list them.
_EXCLUDED = (".coverage", ".coverage.*", "coverage.xml", "coverage.json", "htmlcov/",
             ".pytest_cache/", ".mypy_cache/", ".ruff_cache/", "__pycache__/")


def issue_for_request(project_root, link, target):
    """The slug of the issue in this project that already holds the request,
    or None. The request is the same when the `github:` repository and number
    match, or the stored link is the same text."""
    work = os.path.join(project_root, ".compass", "work")
    try:
        slugs = sorted(os.listdir(work))
    except OSError:
        return None
    found = []
    for slug in slugs:
        try:
            task, _ = load_manifest(os.path.join(work, slug))
        except (CompassError, OSError, ValueError):
            continue
        if not isinstance(task, dict):
            continue
        held = task.get("github") if isinstance(task.get("github"), dict) else {}
        request = task.get("request") if isinstance(task.get("request"), dict) else {}
        same_target = target is not None and (
            str(held.get("repo") or "").lower(), str(held.get("number"))) == (
            str(target[0]).lower(), str(target[1]))
        same_link = bool(link) and str(request.get("link") or "").rstrip("/") == \
            str(link).rstrip("/")
        if same_target or same_link:
            found.append((str(task.get("created") or ""), slug))
    # The newest issue of the request is the one the work goes on in.
    return max(found)[1] if found else None


def hide_run_output(root):
    """Add the patterns of test-run output to `.git/info/exclude`, once. The
    file is local to this clone and is never committed."""
    done = _git(["rev-parse", "--git-path", "info/exclude"], root)
    if done.returncode != 0 or not done.stdout.strip():
        return
    path = os.path.join(root, done.stdout.strip())
    try:
        held = ""
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as fh:
                held = fh.read()
        lines = set(held.splitlines())
        missing = [p for p in _EXCLUDED if p not in lines]
        if not missing:
            return
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(("" if held.endswith("\n") or not held else "\n")
                     + "# test-run output (added by compass)\n" + "\n".join(missing) + "\n")
    except OSError:
        return


def leftovers(root):
    """The changed or untracked paths git still sees, less Compass's own state
    and test-run output."""
    out = _git(["status", "--porcelain", "-z", "--untracked-files=all"], root).stdout
    fields, paths, i = out.split("\0"), [], 0
    while i < len(fields):
        entry = fields[i]
        i += 1
        if len(entry) < 4:
            continue
        if "R" in entry[:2] or "C" in entry[:2]:
            i += 1
        path = entry[3:]
        if path.startswith(".compass/") or _is_generated(path) or _run_output(path):
            continue
        paths.append(path)
    return paths


def current_branch(root):
    return _git(["symbolic-ref", "--short", "-q", "HEAD"], root).stdout.strip() or None


def default_branch(root):
    """The repository's default branch: the one `origin/HEAD` names, else
    `main` or `master` when the name exists."""
    named = _git(["symbolic-ref", "--short", "-q", "refs/remotes/origin/HEAD"], root)
    if named.returncode == 0 and "/" in named.stdout:
        return named.stdout.strip().split("/", 1)[1]
    for name in ("main", "master"):
        if _git(["rev-parse", "--verify", "-q", f"refs/heads/{name}"], root).returncode == 0:
            return name
    return None


def branch_for_first_landing(root, slug):
    """Before a commit that finish makes: when `HEAD` is on the default
    branch, make a branch named after the issue and switch to it, so finish
    never commits to the default branch. Returns the new branch's name, or
    None when the current branch is kept."""
    now = current_branch(root)
    if not now or now != default_branch(root):
        return None
    for name in (slug, slug + "-2", slug + "-3"):
        if _git(["switch", "-c", name], root).returncode == 0:
            return name
    return None


def commit_report(root, branch_note=""):
    """What a session otherwise checks by hand after a commit, in three lines:
    the branch, the commit, its author and file count, and what is left in the
    working tree."""
    shown = _git(["log", "-1", "--format=%h%x00%an%x00%s"], root).stdout.strip().split("\0")
    if len(shown) != 3:
        return []
    short, author, subject = shown
    names = [n for n in _git(["show", "--name-only", "-z", "--format=", "HEAD"],
                             root).stdout.split("\0") if n]
    record = [n for n in names if n.startswith((".compass/", "docs/compass/"))]
    left = leftovers(root)
    subject = subject if len(subject) <= 60 else subject[:57] + "..."
    return [
        f"  commit   : {short} \"{subject}\" by {author}, on branch "
        f"{current_branch(root) or 'detached HEAD'}{branch_note}",
        f"  committed: {len(names)} file(s): {len(names) - len(record)} of the change, "
        f"{len(record)} of the record (.compass/ and docs/compass/, as intended)",
        "  tree     : working tree clean" if not left else
        "  tree     : not committed: " + ", ".join(left[:5])
        + (f" and {len(left) - 5} more" if len(left) > 5 else ""),
    ]


def drop_stale_records(task_dir, scenario_ids):
    """Remove the red and green records of this issue that no scenario of the
    manifest holds now, with their registry entries, so every record left
    names the files as they are. `finish` calls it before it writes the
    records of `scenario_ids`; the next record written drops the removed
    files from `SHA256SUMS`."""
    from compass_pkg.red_first import is_record_name, record_stem
    evidence = os.path.join(task_dir, "evidence")
    keep = {record_stem(kind, sid, "inner") + ".json"
            for kind in ("red", "green") for sid in scenario_ids}
    gone = []
    try:
        names = sorted(os.listdir(evidence))
    except OSError:
        return gone
    for name in names:
        if name in keep or not (is_record_name("red", name) or is_record_name("green", name)):
            continue
        for path in (os.path.join(evidence, name),
                     os.path.join(evidence, name[:-len(".json")] + ".log")):
            try:
                os.remove(path)
            except OSError:
                pass
        gone.append("evidence/" + name)
    if gone:
        task, task_path = load_manifest(task_dir)
        task["evidence"] = [e for e in task.get("evidence") or []
                            if not (isinstance(e, dict) and e.get("path") in gone)]
        save_manifest(task, task_path)
    return gone
