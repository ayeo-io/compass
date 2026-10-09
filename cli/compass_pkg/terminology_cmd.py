"""`compass terminology [term]` - render the v2 vocabulary.

`governance/terminology.yml` is the single source of truth for what every
v2 word means; this verb renders it at the terminal so the answer to any
vocabulary question is one command away. Read-only.
"""
import os
import sys

import yaml

from compass_pkg.core import CompassError, find_compass_dir, find_governance, load_yaml


def _load_terms():
    path = os.path.join(find_governance(), "terminology.yml")
    doc = load_yaml(path)
    if not isinstance(doc, dict) or not isinstance(doc.get("terms"), dict):
        raise CompassError(
            f"{path}: no `terms:` section - the vocabulary file is the "
            "single source of truth, and it is unreadable.")
    return doc


def cmd_terminology(args):
    doc = _load_terms()
    terms = doc["terms"]
    # Codes are the other half of the vocabulary: a reader meeting `TRC-A1`
    # is looking something up just as much as one meeting "initiative". Looked up
    # by their bare prefix, with or without the trailing hyphen.
    codes = doc.get("codes") or {}
    version = doc.get("version", "?")
    if not args.term:
        # The whole glossary is a REPORT: every term is listed, because a
        # glossary that shows a selection is not a glossary. The summary says
        # how many there are and how to look one up, which is what a reader who
        # does not want to scroll actually needs.
        from compass_pkg.terminal import Report

        rep = Report(args, title="the v2 vocabulary")
        rep.summary(
            f"The v2 vocabulary ({version}) - {len(terms)} terms and "
            f"{len(codes)} codes.",
            "Ask for one with `compass terminology <term-or-code>`.")
        rep.section("CODES",
                    [{"code": f"{n}-",
                      "means": " ".join(str(codes[n].get("means", "")).split())}
                     for n in sorted(codes)],
                    lambda r: "%-24s %s" % (r["code"], r["means"][:70]))
        rep.section("TERMS",
                    [{"term": n,
                      "means": str(terms[n].get("means", "")).strip().split("\n")[0]}
                     for n in sorted(terms)],
                    lambda r: "%-24s %s" % (r["term"], r["means"][:70]))
        rep.data(version=version)
        return rep.emit()

    raw = args.term.strip()
    code_key = raw.rstrip("-").upper()
    # A term wins a bare lookup; the code is reachable by its hyphenated form.
    # `adr` exists in both blocks, and checking codes first would make the
    # `adr` term unreachable.
    if code_key in codes and (raw.endswith("-") or raw.lower() not in terms):
        entry = codes[code_key]
        print(f"{code_key}-  (vocabulary {version})")
        print(f"  means:    {' '.join(str(entry.get('means', '')).split())}")
        if entry.get("referent"):
            print(f"  refers to: {' '.join(str(entry['referent']).split())}")
        if entry.get("appears_in"):
            print(f"  appears in: {', '.join(entry['appears_in'])}")
        if entry.get("related"):
            print(f"  related:  {', '.join(entry['related'])}")
        return 0

    key = raw.lower().replace(" ", "-")
    entry = terms.get(key)
    if entry is None:
        near = [n for n in sorted(terms) if key in n or n in key]
        hint = f" Did you mean: {', '.join(near)}?" if near else ""
        raise CompassError(
            f"'{args.term}' is not in the vocabulary.{hint} "
            "Run `compass terminology` to list every term and code.")
    print(f"{key}  (vocabulary {version})")
    means = " ".join(str(entry.get("means", "")).split())
    print(f"  means:   {means}")
    if entry.get("github"):
        print(f"  github:  {entry['github']}")
    if entry.get("also"):
        print(f"  also:    {entry['also']}")
    if entry.get("related"):
        print(f"  related: {', '.join(entry['related'])}")
    return 0


# --- the derived glossary ---------------------------------------------------
# docs/glossary.md is generated from governance/terminology.yml so the page a
# reader opens and the file the build enforces cannot disagree. A hand-written
# copy of a machine-readable source goes out of date when the source changes.
#
# Private, like _derive-system-spec: called at ship, not a public verb.

def _fmt(value):
    """One field, flattened. YAML block scalars arrive with newlines in them."""
    if isinstance(value, list):
        return ", ".join(f"`{v}`" for v in value)
    return " ".join(str(value).split())


def render_glossary(vocab: dict) -> str:
    terms = vocab.get("terms") or {}
    codes = vocab.get("codes") or {}
    out = [
        "# Glossary",
        "",
        "Every word and every id prefix Compass uses, with what it means.",
        "",
        "**This page is generated** from `governance/terminology.yml`. Edit that",
        "file, not this one - a drift guard fails the build if the two disagree.",
        "",
        "## Codes",
        "",
        "The short ids that appear in artifacts. If you have met one in a spec or",
        "a pull request and wondered what it was, it is here.",
        "",
    ]
    for code in sorted(codes):
        e = codes[code] or {}
        out.append(f"### `{code}-`")
        out.append("")
        out.append(_fmt(e.get("means", "")))
        out.append("")
        out.append(f"**Refers to:** {_fmt(e.get('referent', ''))}")
        out.append("")
        if e.get("appears_in"):
            out.append(f"**Appears in:** {_fmt(e['appears_in'])}")
            out.append("")
        if e.get("related"):
            out.append(f"**Related:** {_fmt(e['related'])}")
            out.append("")
    out += ["## Terms", ""]
    for term in sorted(terms):
        e = terms[term] or {}
        out.append(f"### {term}")
        out.append("")
        out.append(_fmt(e.get("means", "")))
        out.append("")
        for label, key in (("Also", "also"),
                           ("GitHub", "github"), ("Related", "related")):
            if e.get(key):
                out.append(f"**{label}:** {_fmt(e[key])}")
                out.append("")
    return "\n".join(out).rstrip("\n") + "\n"


def cmd_derive_glossary(args):
    root = os.path.dirname(find_compass_dir()) if not getattr(args, "root", None) else args.root
    src = os.path.join(root, "governance", "terminology.yml")
    if not os.path.isfile(src):
        raise CompassError(f"no vocabulary file at {src}")
    with open(src, "r", encoding="utf-8") as fh:
        vocab = yaml.safe_load(fh) or {}
    text = render_glossary(vocab)
    out = getattr(args, "out", None) or os.path.join(root, "docs", "glossary.md")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(text)
    print(f"compass _derive-glossary: {out} derived "
          f"({len(vocab.get('codes') or {})} codes, {len(vocab.get('terms') or {})} terms).")
    return 0
