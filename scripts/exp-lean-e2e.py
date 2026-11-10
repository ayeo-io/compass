#!/usr/bin/env python3
"""Play the agent's part of the lean path with no model, and check the record.

This is the proof for the experiment branch `exp-lean`. For two cases, an
unlabeled change and a `personal-data` change, it:

1. makes a small Python package with a pytest suite in a new git repository
   with a bare `origin`;
2. runs the command sequence of `commands/assess.md`, counting each
   `compass` command the agent runs;
3. answers each approval request as a person at a terminal does, with
   `compass evidence approve` on a pseudo-terminal (the sdd-bench harness
   does the same);
4. squash-merges the branch into `main`, as the sdd-bench harness does;
5. runs the sdd-bench record checker on the result and prints its output.

It also sends the pre-tool hook a code edit before and after the `specify`
approval of the labeled case, to show the hook refuses the first.

Usage:
  python3 scripts/exp-lean-e2e.py [--checker PATH] [--keep]

Exit status: 0 when both records pass all six checks and each case used at
most five `compass` commands.
"""
from __future__ import annotations

import argparse
import json
import os
import pty
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COMPASS = str(ROOT / "bin" / "compass")
HOOK = str(ROOT / "hooks" / "pre-tool.sh")
APPROVER = "exp-lean-approver"
PYTEST = [sys.executable, "-m", "pytest", "-q"]
REQUEST_REPO, REQUEST_NUMBER, REQUESTER = "acme/shop", 7, "Sam Taylor"

ENV = dict(os.environ, GIT_AUTHOR_NAME="Dev", GIT_AUTHOR_EMAIL="dev@example.com",
           GIT_COMMITTER_NAME="Dev", GIT_COMMITTER_EMAIL="dev@example.com")
ENV.pop("CLAUDE_PLUGIN_ROOT", None)
ENV.pop("CLAUDE_PROJECT_DIR", None)
# The agent's Bash tool has the plugin's bin/ on PATH, and the hook reads the CLI there.
ENV["PATH"] = str(ROOT / "bin") + os.pathsep + ENV["PATH"]


def sh(argv, cwd, check=True):
    done = subprocess.run(argv, cwd=cwd, env=ENV, capture_output=True, text=True)
    if check and done.returncode != 0:
        sys.exit(f"FAILED: {' '.join(map(str, argv))}\n{done.stdout}{done.stderr}")
    return done


class Agent:
    """The agent: it runs `compass` commands, and each one is counted."""

    def __init__(self, repo):
        self.repo, self.commands = repo, []

    def compass(self, *args, expect=0):
        done = sh([COMPASS, *args], self.repo, check=False)
        self.commands.append("compass " + " ".join(
            a if " " not in a else f'"{a}"' for a in args))
        print(f"$ {self.commands[-1]}")
        print("".join("    " + line + "\n" for line in
                      (done.stdout + done.stderr).splitlines()), end="")
        if done.returncode != expect:
            sys.exit(f"FAILED: exit {done.returncode}, expected {expect}")
        return done.stdout


def person_approves(repo):
    """The person at a terminal: answer each pending request, on a pseudo-terminal."""
    import yaml
    answered = []
    for path in sorted(repo.glob(".compass/work/*/approval-requests/pending/*.yml")):
        request = yaml.safe_load(path.read_text(encoding="utf-8"))
        marker = path.with_suffix(".answered")
        if marker.exists():
            continue
        form, value = request["form"], request.get("value")
        argv = [COMPASS, "evidence", "approve", "--issue", str(request["issue"])]
        argv += [f"--{form}"] if form in ("decisions", "ship") else [f"--{form}", str(value)]
        argv += ["--approver", APPROVER, "--role", "owner"]
        if request.get("scope"):
            argv += ["--scope", str(request["scope"])]
        pid, fd = pty.fork()
        if pid == 0:
            try:
                os.chdir(repo)
                os.execve(argv[0], argv, ENV)
            finally:
                os._exit(127)
        out = b""
        while True:
            try:
                chunk = os.read(fd, 4096)
            except OSError:
                break
            if not chunk:
                break
            out += chunk
        os.close(fd)
        code = os.waitstatus_to_exitcode(os.waitpid(pid, 0)[1])
        first = out.decode("utf-8", "replace").strip().splitlines()[:1]
        print(f"  [person] approves request {request['number']} ({form}"
              f"{' ' + str(value) if value else ''}): exit {code} {first[0] if first else ''}")
        if code != 0:
            sys.exit("FAILED: the person's approval was refused\n" + out.decode())
        marker.write_text("answered\n", encoding="utf-8")
        answered.append(request["number"])
    return answered


def hook_verdict(repo, target):
    """The pre-tool hook's exit code for an Edit of `target`: 2 is a refusal."""
    event = {"tool_name": "Edit", "session_id": "exp-lean-e2e", "cwd": str(repo),
             "tool_input": {"file_path": str(repo / target), "old_string": "a",
                            "new_string": "b"}}
    done = subprocess.run(["bash", HOOK], cwd=repo, env=dict(ENV, CLAUDE_PROJECT_DIR=str(repo)),
                          input=json.dumps(event), capture_output=True, text=True)
    return done.returncode, (done.stderr.strip().splitlines() or [""])[0]


def make_repo(folder):
    repo = folder / "repo"
    (repo / "shop").mkdir(parents=True)
    (repo / "tests").mkdir()
    (repo / "shop" / "__init__.py").write_text("")
    (repo / "shop" / "orders.py").write_text(
        "def total(prices):\n    return sum(prices)\n")
    (repo / "shop" / "users.py").write_text(
        "USERS = {}\n\n\ndef add_user(name, email):\n    USERS[name] = {\"email\": email}\n")
    (repo / "tests" / "test_orders.py").write_text(
        "from shop.orders import total\n\n\ndef test_total():\n    assert total([1, 2]) == 3\n")
    (repo / "pytest.ini").write_text("[pytest]\ntestpaths = tests\n")
    (repo / ".gitignore").write_text("__pycache__/\n.pytest_cache/\n")
    # The person who approves is the project's owner.
    (repo / "compass.yml").write_text(f"owner: {APPROVER}\n")
    sh(["git", "init", "-q", "-b", "main"], repo)
    sh(["git", "add", "-A"], repo)
    sh(["git", "commit", "-q", "-m", "Initial commit"], repo)
    sh(["git", "init", "-q", "--bare", str(folder / "origin.git")], folder)
    sh(["git", "remote", "add", "origin", str(folder / "origin.git")], repo)
    sh(["git", "push", "-q", "-u", "origin", "main"], repo)
    return repo


def squash_merge(repo, branch, number):
    """Merge `branch` into main as GitHub's squash merge does (sdd-bench `_sdd_merge`)."""
    head = sh(["git", "rev-parse", branch], repo).stdout.strip()
    main = sh(["git", "rev-parse", "refs/heads/main"], repo).stdout.strip()
    subject = sh(["git", "log", "-1", "--format=%s", head], repo).stdout.strip()
    tree = sh(["git", "rev-parse", f"{head}^{{tree}}"], repo).stdout.strip()
    merge = sh(["git", "commit-tree", tree, "-p", main, "-m", f"{subject} (#{number})"],
               repo).stdout.strip()
    sh(["git", "update-ref", "refs/heads/main", merge, main], repo)
    sh(["git", "push", "-q", "origin", "main"], repo)
    return merge


def check_record(repo, checker):
    base = sh(["git", "rev-list", "--max-parents=0", "main"], repo).stdout.split()[-1]
    done = sh([sys.executable, checker, "--workspace", str(repo), "--branch", "main",
               "--base", base, "--expect-request", f"{REQUEST_REPO}#{REQUEST_NUMBER}",
               "--require-ship-approval"], repo, check=False)
    print(done.stdout.rstrip())
    return done.returncode


def write_discount(repo):
    with (repo / "shop" / "orders.py").open("a") as fh:
        fh.write("\n\ndef discounted(prices, percent):\n"
                 "    return total(prices) * (100 - percent) / 100\n")
    (repo / "tests" / "test_discount.py").write_text(
        "from shop.orders import discounted\n\n\n"
        "def test_a_discount_reduces_the_total():\n"
        "    assert discounted([100], 10) == 90\n")


def write_forget_user(repo):
    with (repo / "shop" / "users.py").open("a") as fh:
        fh.write("\n\ndef forget_user(name):\n    return USERS.pop(name, None) is not None\n")
    (repo / "tests" / "test_forget_user.py").write_text(
        "from shop import users\n\n\n"
        "def test_a_forgotten_user_has_no_row():\n"
        "    users.add_user('ann', 'ann@example.com')\n"
        "    assert users.forget_user('ann') is True\n"
        "    assert 'ann' not in users.USERS\n\n\n"
        "def test_forgetting_an_unknown_user_changes_nothing():\n"
        "    assert users.forget_user('nobody') is False\n")


def case_unlabeled(folder, checker):
    print("\n=== case (a): an unlabeled change ===")
    repo = make_repo(folder)
    agent = Agent(repo)
    agent.compass("quick-fix", "start", "discount",
                  "--intent", "An order total can take a percentage discount",
                  "--request", f"https://github.com/{REQUEST_REPO}/issues/{REQUEST_NUMBER}",
                  "--requester", REQUESTER)
    code, _ = hook_verdict(repo, "shop/orders.py")
    print(f"  [hook] a code edit with no red on record: exit {code} (0 allows it)")
    if code != 0:
        sys.exit("FAILED: the hook refused a code edit on an unlabeled issue")
    write_discount(repo)
    print("$ python3 -m pytest -q    (the agent runs the tests directly)")
    sh(PYTEST, repo)
    agent.compass("quick-fix", "finish", "-m", "Add a percentage discount to the total (#7)",
                  "--", *PYTEST)
    person_approves(repo)
    print("  [person] That is what I asked for. Commit it on a new branch.")
    sh(["git", "switch", "-q", "-c", "discount-7"], repo)
    print("$ git switch -c discount-7")
    agent.compass("ship-commit")
    squash_merge(repo, "discount-7", REQUEST_NUMBER + 1)
    print(f"  [person] merged pull request #{REQUEST_NUMBER + 1} into main")
    return agent, check_record(repo, checker)


def case_labeled(folder, checker):
    print("\n=== case (b): a change labeled personal-data ===")
    repo = make_repo(folder)
    agent = Agent(repo)
    out = agent.compass("quick-fix", "start", "forget-user",
                        "--intent", "A user can be forgotten: their row is deleted",
                        "--labels", "personal-data",
                        "--request",
                        f"https://github.com/{REQUEST_REPO}/issues/{REQUEST_NUMBER}",
                        "--requester", REQUESTER)
    spec = next(repo.glob("docs/compass/*-forget-user/acceptance-criteria.md"))
    assert str(spec.relative_to(repo)) in out
    # The agent writes the scenarios in the acceptance criteria, and nowhere else.
    text = spec.read_text(encoding="utf-8")
    marker = "## Non-functional requirements"
    extra = ("### Scenario: Forgetting an unknown user changes nothing\n"
             "<!-- traceability id: TRC-002 · serves: INT-1 -->\n\n"
             "```gherkin\nScenario: TRC-002\n  Given no user named nobody\n"
             "  When nobody is forgotten\n  Then nothing changes\n```\n\n")
    spec.write_text(text.replace(marker, extra + marker), encoding="utf-8")
    print(f"  (the agent adds scenario TRC-002 to {spec.relative_to(repo)})")
    agent.compass("evidence", "request", "--checkpoint", "specify")
    code, why = hook_verdict(repo, "shop/users.py")
    print(f"  [hook] a code edit before the specify approval: exit {code} - {why}")
    if code != 2:
        sys.exit("FAILED: the hook allowed a code edit before the specify approval")
    person_approves(repo)
    code, _ = hook_verdict(repo, "shop/users.py")
    print(f"  [hook] a code edit after the specify approval: exit {code} (0 allows it)")
    if code != 0:
        sys.exit("FAILED: the hook refused a code edit after the specify approval")
    write_forget_user(repo)
    print("$ python3 -m pytest -q    (the agent runs the tests directly)")
    sh(PYTEST, repo)
    agent.compass("quick-fix", "finish", "-m", "Let a user be forgotten (#7)", "--", *PYTEST)
    person_approves(repo)
    print("  [person] That is what I asked for. Commit it on a new branch.")
    sh(["git", "switch", "-q", "-c", "forget-user-7"], repo)
    print("$ git switch -c forget-user-7")
    agent.compass("ship-commit")
    squash_merge(repo, "forget-user-7", REQUEST_NUMBER + 1)
    print(f"  [person] merged pull request #{REQUEST_NUMBER + 1} into main")
    return agent, check_record(repo, checker)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--checker", default=os.path.expanduser(
        "~/dev/sdd-bench/tools/check_record.py"), help="the sdd-bench record checker")
    parser.add_argument("--keep", action="store_true", help="keep the temporary repositories")
    args = parser.parse_args()
    holder = Path(tempfile.mkdtemp(prefix="exp-lean-e2e-"))
    failed = False
    try:
        for name, case in (("unlabeled", case_unlabeled), ("personal-data", case_labeled)):
            folder = holder / name
            folder.mkdir()
            agent, code = case(folder, args.checker)
            print(f"--- {name}: {len(agent.commands)} compass command(s), "
                  f"check_record exit {code}")
            for command in agent.commands:
                print(f"    {command}")
            failed = failed or code != 0 or len(agent.commands) > 5
    finally:
        if args.keep:
            print(f"kept: {holder}")
        else:
            shutil.rmtree(holder, ignore_errors=True)
    print("\nRESULT:", "FAIL" if failed else "PASS")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
