"""`quick-fix finish` traces a changed tracked file under `.compass/`.

`finish` traced every changed path outside `.compass/`, then ran
`ship-commit`. A tracked file inside it, such as `.compass/config.yml`, was
left untraced, so ship refused it as outside the issue's scope after the
full suite had run (#321). Only untracked issue state under `.compass/`
stays out.

Scenario id: FT-1 (issue `finish-traces-compass-files`).
"""
from __future__ import annotations

from test_quick_fix_verbs import (_finish, _git, _ready_to_finish,  # noqa: F401
                                  repo)


def test_ft_1_a_tracked_compass_file_lands_with_one_finish(repo):
    config = repo / ".compass" / "config.yml"
    config.parent.mkdir(exist_ok=True)
    config.write_text("mode: enforced\n")
    _git(repo, "add", ".compass/config.yml")
    _git(repo, "commit", "-q", "-m", "config")
    _ready_to_finish(repo, "fix-greeting")
    config.write_text("mode: enforced\nproject: {}\n")
    result = _finish(repo, "fix-greeting")
    assert result.returncode == 0, result.stdout + result.stderr
    committed = _git(repo, "show", "--name-only", "--format=", "HEAD~1")
    assert ".compass/config.yml" in committed, committed
    assert ".compass/work/" not in committed.replace(
        ".compass/work/fix-greeting/", ""), committed
