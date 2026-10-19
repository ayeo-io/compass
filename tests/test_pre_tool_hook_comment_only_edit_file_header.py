"""A comment Edit is code when the file header or a tool directive says so.

The comment-only check compares syntax trees and YAML events. Two things act
on a file before that comparison means anything:

* The encoding cookie of a Python file (PEP 263: a comment on line 1, or on
  line 2 when line 1 is blank or a comment, that matches `coding[:=]` and a
  name). Python decodes the source with that name before it parses a line. A
  file that says `utf-7` or `unicode_escape` decodes `+AAo-` or `\\x0a` to a
  line break, so text inside a comment becomes code. Two comment lines put
  above a cookie on line 2 move it out of the first two lines and change how
  Python reads the file.
* A comment that a tool reads as a directive. The pragma list is a deny list of
  words, so a tool that is not on it passes. The words below are the common
  ones, and a cloud-init file whose first line is `## template: jinja` is
  rendered as a template before the YAML parser sees it.

Each refusal below ends in `no-red-on-record`, the refusal the hook gave before
the comment-only check existed. The allowed cases show that the rule is not
wider than it needs to be.

Scenario ids: see hooks-comment-only-edits-and-prose/acceptance-criteria.md.
"""
from __future__ import annotations

import pytest

from test_pre_tool_hook_comment_only_edit import (
    CI, PY, _allowed, _edit, _mutant, _project, _refused, _run_mutant, _write)

UTF7 = "# coding: utf-7\nx = 1  # note\n"


@pytest.mark.parametrize("text, old, new", [
    pytest.param(UTF7, "# note", '# note +AAo-print("x")', id="utf-7-line-break"),
    pytest.param("# coding: unicode_escape\nx = 1  # note\n", "# note",
                 '# note \\x0aprint("x")', id="unicode-escape-line-break"),
    pytest.param("# vim: set fileencoding=latin-1 :\nx = 1  # note\n", "# note",
                 "# note again", id="latin-1-in-a-modeline-style-cookie"),
    pytest.param("# -*- coding: UTF-7 -*-\nx = 1  # note\n", "# note", "# other",
                 id="name-in-capitals"),
    pytest.param("#!/usr/bin/env python3\n# coding: cp037\nx = 1  # note\n",
                 "# note", "# other", id="cookie-on-line-two-after-a-shebang"),
    pytest.param("﻿# coding: utf-7\nx = 1  # note\n", "# note", "# other",
                 id="cookie-after-a-byte-order-mark"),
])
def test_comment_edit_of_a_file_whose_encoding_cookie_is_not_utf_8_or_ascii_is_refused(
        tmp_path, text, old, new):
    """Scenario id: `TRC-062` in hooks-comment-only-edits-and-prose/acceptance-criteria.md"""
    root = _project(tmp_path)

    _refused(_edit(root, PY, old, new, text=text))


@pytest.mark.parametrize("text, old, new", [
    # The cookie line is not among the changed lines, so the pragma test does
    # not see it: only a comparison of the cookie before and after does.
    pytest.param("# a\n# coding: utf-8\nx = 1\n", "# a\n", "# z\n# z\n# a\n",
                 id="cookie-moves-to-line-four"),
    pytest.param("# header\nx = 1\n", "# header\n",
                 "# header\n# coding: utf-8\n", id="cookie-is-added"),
    pytest.param("# coding: utf-8\nx = 1\n", "# coding: utf-8\n", "",
                 id="cookie-is-removed"),
    pytest.param("# coding: ascii\nx = 1\n", "# coding: ascii", "# coding: utf-8",
                 id="cookie-name-changes"),
])
def test_comment_edit_that_changes_the_encoding_cookie_of_a_file_is_refused(
        tmp_path, text, old, new):
    """Scenario id: `TRC-062` in hooks-comment-only-edits-and-prose/acceptance-criteria.md"""
    root = _project(tmp_path)

    _refused(_edit(root, PY, old, new, text=text))


@pytest.mark.parametrize("text", [
    pytest.param("# -*- coding: utf-8 -*-\nx = 1  # note\n", id="utf-8"),
    pytest.param("# coding: UTF_8\nx = 1  # note\n", id="utf-8-in-capitals"),
    pytest.param("# vim: set fileencoding=utf8 :\nx = 1  # note\n", id="utf8-modeline"),
    pytest.param("#!/usr/bin/env python3\n# coding: ascii\nx = 1  # note\n",
                 id="ascii-after-a-shebang"),
    pytest.param("x = 1  # note\n", id="no-cookie"),
    pytest.param("x = 1\n# coding: latin-1\ny = 2  # note\n",
                 id="line-two-is-not-a-cookie-after-a-line-of-code"),
])
def test_comment_edit_of_a_file_with_a_utf_8_ascii_or_no_cookie_is_allowed(tmp_path, text):
    """Scenario id: `TRC-062` in hooks-comment-only-edits-and-prose/acceptance-criteria.md"""
    root = _project(tmp_path)

    _allowed(_edit(root, PY, "# note", "# another note", text=text))


@pytest.mark.parametrize("comment", [
    pytest.param("# nosemgrep: python.lang.rule", id="nosemgrep"),
    pytest.param("# gitleaks:allow", id="gitleaks"),
    pytest.param("# checkov:skip=CKV_AWS_1: reason", id="checkov"),
    pytest.param("# lgtm[py/unused-import]", id="lgtm"),
    pytest.param("# NOSONAR", id="nosonar"),
    pytest.param("# codeql[py/path-injection]", id="codeql"),
    pytest.param("# yapf: disable", id="yapf"),
    pytest.param("# tfsec:ignore:aws-s3-enable-logging", id="tfsec"),
    pytest.param("# trivy:ignore:CVE-2026-0001", id="trivy"),
])
def test_comment_that_carries_a_scanner_or_formatter_directive_is_code(tmp_path, comment):
    """Scenario id: `TRC-063` in hooks-comment-only-edits-and-prose/acceptance-criteria.md"""
    root = _project(tmp_path)

    _refused(_edit(root, PY, "x = 1", f"x = 1  {comment}", text="x = 1\n"))


@pytest.mark.parametrize("text", [
    pytest.param("## template: jinja\n#cloud-config\na: 1  # note\n", id="jinja"),
    pytest.param("  # Template : jinja\na: 1  # note\n", id="loose-spacing"),
])
def test_comment_edit_of_a_file_that_starts_as_a_template_is_refused(tmp_path, text):
    """Scenario id: `TRC-063` in hooks-comment-only-edits-and-prose/acceptance-criteria.md"""
    root = _project(tmp_path)

    _refused(_edit(root, CI, "# note", '# note {{ "\\nevil: true" }}', text=text))


def test_comment_edit_that_adds_a_template_first_line_is_refused(tmp_path):
    """Scenario id: `TRC-063` in hooks-comment-only-edits-and-prose/acceptance-criteria.md"""
    root = _project(tmp_path)

    _refused(_edit(root, CI, "a: 1", "## template: jinja\na: 1",
                   text="a: 1  # note\n"))


def test_the_word_template_in_a_later_comment_is_not_a_template_header(tmp_path):
    """Scenario id: `TRC-063` in hooks-comment-only-edits-and-prose/acceptance-criteria.md"""
    root = _project(tmp_path)

    _allowed(_edit(root, CI, "# note", "# see the template: below",
                   text="a: 1  # note\n"))


# ---------------------------------------------------------------------------
# Mutation proofs: break one rule in a copy of the check and show the hook then
# lets through the call its twin above refuses.
# ---------------------------------------------------------------------------

_UNSAFE_CHECK = ("    if cookie_before is not None and cookie_before not in SAFE_ENCODINGS:\n"
                 "        return True\n")
_MOVED_CHECK = ("    if cookie_before != cookie_after:\n"
                "        return True\n")
_TEMPLATE_CHECK = ('    if starts_as_template(before) or starts_as_template(after):\n'
                   '        return no("template")\n')

FAULTS = [
    pytest.param({_UNSAFE_CHECK: ""}, PY, UTF7, "# note", '# note +AAo-print("x")',
                 id="TRC-062-an-unsafe-cookie-is-allowed"),
    pytest.param({_MOVED_CHECK: ""}, PY, "# a\n# coding: utf-8\nx = 1\n",
                 "# a\n", "# z\n# z\n# a\n",
                 id="TRC-062-a-moved-cookie-is-allowed"),
    pytest.param({_TEMPLATE_CHECK: ""}, CI, "## template: jinja\na: 1  # note\n",
                 "# note", '# note {{ "\\nevil: true" }}',
                 id="TRC-063-a-template-first-line-is-allowed"),
] + [
    pytest.param({f"|{word}": ""}, PY, "x = 1\n", "x = 1", f"x = 1  # {comment}",
                 id=f"TRC-063-{word}-is-not-a-directive")
    for word, comment in (("nosemgrep", "nosemgrep: r"), ("gitleaks", "gitleaks:allow"),
                          ("checkov", "checkov:skip=1"), ("lgtm", "lgtm[x]"),
                          ("nosonar", "NOSONAR"), ("codeql", "codeql[x]"),
                          ("yapf", "yapf: disable"), ("tfsec", "tfsec:ignore:x"),
                          ("trivy", "trivy:ignore:x"))
]


@pytest.mark.parametrize("module, rel, text, old, new", FAULTS)
def test_a_fault_in_the_header_rules_lets_through_the_call_its_twin_refuses(
        tmp_path, module, rel, text, old, new):
    """Supports `TRC-062` and `TRC-063`: with the fault planted the hook allows
    what the scenario's test says it refuses."""
    root = _project(tmp_path)
    _write(root, rel, text)
    hook = _mutant(tmp_path, module=module)

    status, err, _ = _run_mutant(hook, root, rel, old, new)

    assert status == 0, (status, err)
