"""`redact` removes secret values and never a key name.

A landed issue record is copied to the delivery record through `redact`, and
each copy must equal its source apart from real secrets. A key whose name
only contains a secret word, such as `secret-scan-declared` or
`input_tokens`, names no secret: its text and the line after it stay as they
are. A value after a key that names a secret, such as `password` or
`GITHUB_TOKEN`, is still replaced.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "cli"))
from compass_pkg.redact import MARK, redact  # noqa: E402

READINESS_CATALOGUE = Path(__file__).resolve().parent.parent / (
    "governance/presets/default/readiness.yml")


@pytest.mark.parametrize("text", [
    # A key followed by a nested key on the next line.
    "signals:\n  secret-scan-declared:\n    statement: The project declares it.\n",
    "secret-scan-declared:\n  steps:\n    - one\n",
    # Ordinary values under keys that only contain a secret word.
    "secret-scan-declared: present\n",
    "secret_scan: scanner-name\n",
    "usage: {input_tokens: 123456, output_tokens: 7890}\n",
    "cache_creation_input_tokens: 40000\n",
    "max_tokens=4096\n",
    "token_count: 1234\n",
    "params: {key: secret_scan}\n",
    "a .compass/work/reset-password/acceptance-criteria.feature path\n",
])
def test_trc_001_a_key_name_and_an_ordinary_value_are_never_redacted(text):
    assert redact(text, env={}) == text


def test_trc_001_the_readiness_catalogue_passes_through_unchanged():
    text = READINESS_CATALOGUE.read_text(encoding="utf-8")
    assert "secret-scan-declared:" in text
    assert redact(text, env={}) == text


@pytest.mark.parametrize("text, kept", [
    ("password: hunter2-not-real", "password: "),
    ("db_password=hunter2-not-real", "db_password="),
    ("GITHUB_TOKEN=abcdefgh12345678", "GITHUB_TOKEN="),
    ("ANTHROPIC_API_KEY: abcdefgh12345678", "ANTHROPIC_API_KEY: "),
    ("api-key = abcdefgh12345678", "api-key = "),
    ('{"client_secret": "abcdefgh12345678"}', '{"client_secret": "'),
    ("SECRET_KEY=abcdefgh12345678", "SECRET_KEY="),
    ("AWS_SECRET_ACCESS_KEY=abcdefgh12345678", "AWS_SECRET_ACCESS_KEY="),
    ("token: abcdefgh12345678", "token: "),
])
def test_trc_001_a_value_after_a_secret_key_on_its_line_is_redacted(text, kept):
    out = redact(text, env={})
    assert out.startswith(kept + MARK), out
    assert "abcdefgh12345678" not in out and "hunter2-not-real" not in out


@pytest.mark.parametrize("secret", [
    "sk-ant-api03-FAKEfakeFAKEfake0123456789abcdef",
    "ghp_FAKEfakeFAKEfake0123",
    "github_pat_FAKEfake_FAKEfake0123",
    "AKIAABCDEFGHIJKLMNOP",
])
def test_trc_001_a_credential_shape_is_still_redacted(secret):
    assert redact(f"error: {secret} refused", env={}) == f"error: {MARK} refused"


def test_trc_001_a_bearer_token_and_an_environment_value_are_still_redacted():
    out = redact("Authorization: Bearer abcdefgh12345678 and hunter2-env-value",
                 env={"SERVICE_TOKEN": "hunter2-env-value"})
    assert "abcdefgh12345678" not in out and "hunter2-env-value" not in out


# --- a secret value on the lines after its key --------------------------------

@pytest.mark.parametrize("text, secret", [
    ("db:\n  password: |\n    plain passphrase one\n    second line\nnext: kept\n",
     "plain passphrase"),
    ("token:\n  plain passphrase two\nnext: kept\n", "plain passphrase"),
    ("secret_key: >-\n  plain passphrase\n  folded on\nnext: kept\n",
     "plain passphrase"),
    ("password: |2-\n\n    plain passphrase after a blank\nnext: kept\n",
     "plain passphrase"),
])
def test_trc_001_a_block_value_after_a_secret_key_is_redacted(text, secret):
    out = redact(text, env={})
    assert secret not in out and "second line" not in out and "folded on" not in out
    assert MARK in out
    # The key and the next key at the same or a lower indentation stay.
    assert out.endswith("next: kept\n"), out
    assert out.count("\n") == text.count("\n"), out


@pytest.mark.parametrize("text", [
    "token:\nsibling: kept\n",
    "signals:\n  password:\n  statement: kept\n",
    "password: |\nsibling: kept\n",
])
def test_trc_001_a_secret_key_followed_by_a_sibling_key_is_unchanged(text):
    assert redact(text, env={}) == text
