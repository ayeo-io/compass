#!/usr/bin/env python3
# =============================================================================
# compass_pkg.review_rules - `compass review-rule list`, and its lint
# =============================================================================
#
# Review rules are data: governance/review-rules.yml holds one rule per
# incident, scoped to the files it applies to, with what not to flag. A
# reviewer asks for the rules that match the files a change touches, so it
# reads a short list instead of every house rule, and can cite each finding
# by its RR- id.
#
# The file is read from the project's own governance/, never the shipped
# copy: the Compass repository's rules name Compass's files and incidents,
# and an adopter must not be reviewed against them.
#
# DEPENDENCY: PyYAML, bundled at cli/vendor/yaml/, through core.load_yaml.
# =============================================================================

import fnmatch
import os
import re

from compass_pkg.core import CompassError, FRAMEWORK_ROOT, find_compass_dir, load_yaml

RULES_FILE = os.path.join("governance", "review-rules.yml")
_ID = re.compile(r"RR-\d{3}")
_STRATEGY = re.compile(r"\(`(S\d+)`\)")
MAX_RULE_WORDS = 150


def _known_ids(gov):
    """The guardrail and strategy ids a rule may name in `enforces`."""
    from compass_pkg import effective
    ids = set()
    view = effective.view_or_legacy(start=gov)
    if view is not None:
        ids |= {str(i) for i in view.known_ids()}
    else:
        gr = load_yaml(os.path.join(gov, "guardrails.yml"))
        for key in ("defaults", "project"):
            for g in gr.get(key) or []:
                if isinstance(g, dict) and g.get("id"):
                    ids.add(str(g["id"]))
    for d in (gov, os.path.join(FRAMEWORK_ROOT, "governance")):
        path = os.path.join(d, "strategies.md")
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as fh:
                ids.update(_STRATEGY.findall(fh.read()))
            break
    return ids


def lint_errors(gov):
    """Errors in `<gov>/review-rules.yml`, each naming the rule and the field.
    An absent file has none: the rules are optional."""
    path = os.path.join(gov, "review-rules.yml")
    if not os.path.isfile(path):
        return []
    try:
        data = load_yaml(path)
    except CompassError as exc:
        return [f"[review-rules.yml] {exc}"]
    rules = data.get("rules") if isinstance(data, dict) else None
    if not isinstance(rules, list):
        return ["[review-rules.yml] needs a top-level `rules:` list"]
    known = _known_ids(gov)
    errs, seen = [], set()
    for n, r in enumerate(rules, 1):
        where = f"[review-rules.yml] rule {n}"
        if not isinstance(r, dict):
            errs.append(f"{where}: is not a mapping")
            continue
        rid = r.get("id")
        if not (isinstance(rid, str) and _ID.fullmatch(rid)):
            errs.append(f"{where}: id {rid!r} is not RR- and three digits")
        else:
            where = f"[review-rules.yml] {rid}"
            if rid in seen:
                errs.append(f"{where}: id is repeated")
            seen.add(rid)
        if not isinstance(r.get("blocking"), bool):
            errs.append(f"{where}: blocking must be true or false")
        pats = r.get("file_patterns")
        if not (isinstance(pats, list) and pats
                and all(isinstance(p, str) and p.strip() for p in pats)):
            errs.append(f"{where}: file_patterns must be a non-empty list of strings")
        enf = r.get("enforces")
        if not (isinstance(enf, str) and enf in known):
            errs.append(f"{where}: enforces {r.get('enforces')!r} is not a guardrail "
                        f"or strategy id ({', '.join(sorted(known))})")
        text = r.get("rule")
        if not (isinstance(text, str) and text.strip()):
            errs.append(f"{where}: rule is empty")
        elif len(text.split()) > MAX_RULE_WORDS:
            errs.append(f"{where}: rule has {len(text.split())} words; the limit "
                        f"is {MAX_RULE_WORDS}")
        allowed = r.get("allowed") or []
        if not (isinstance(allowed, list) and all(isinstance(a, str) for a in allowed)):
            errs.append(f"{where}: allowed must be a list of strings")
        inc = r.get("incident")
        if not (isinstance(inc, str) and inc.strip()):
            errs.append(f"{where}: incident is empty; a rule needs the event "
                        f"that justifies it")
    return errs


def matching_rules(rules, files):
    """[(rule, [files it matched])] in id order, each rule once."""
    out = []
    for r in sorted(rules, key=lambda r: str(r.get("id"))):
        hit = [f for f in files
               if any(fnmatch.fnmatchcase(f, p) for p in r.get("file_patterns") or [])]
        if hit:
            out.append((r, hit))
    return out


def _render(rule, files):
    kind = "blocking" if rule.get("blocking") else "not blocking"
    lines = [f"## {rule['id']} ({kind}, enforces {rule.get('enforces')})",
             f"Files: {', '.join(files)}",
             " ".join(str(rule.get("rule", "")).split())]
    allowed = rule.get("allowed") or []
    if allowed:
        lines.append("Do not flag: " + " ".join(allowed))
    lines.append("Incident: " + " ".join(str(rule.get("incident", "")).split()))
    return "\n".join(lines)


def cmd_policy_review_rules(args):
    if args.rules:
        path = args.rules
        if not os.path.isfile(path):
            raise CompassError(f"--rules {path}: no such file.")
    else:
        path = os.path.join(os.path.dirname(find_compass_dir()), RULES_FILE)
        if not os.path.isfile(path):
            print(f"compass review-rule list: this project has no "
                  f"{RULES_FILE}, so no review rule applies.")
            return 0
    data = load_yaml(path)
    rules = data.get("rules") if isinstance(data, dict) else None
    if not isinstance(rules, list):
        raise CompassError(f"{path} needs a top-level `rules:` list. "
                           f"Run `compass policy lint`.")
    files = [os.path.normpath(f).replace(os.sep, "/") for f in args.changed_files]
    found = matching_rules([r for r in rules if isinstance(r, dict)], files)
    if not found:
        print("compass review-rule list: no review rule applies to these files.")
        return 0
    print("\n\n".join(_render(r, hit) for r, hit in found))
    return 0


def register(sub):
    """Add the `compass review-rule` group, with `list`."""
    group = sub.add_parser("review-rule", help="the project's review rules")
    p = group.add_subparsers(dest="review_rule_cmd", required=True).add_parser(
        "list", help="print the review rules that apply to the changed files")
    p.add_argument("--changed-files", nargs="+", required=True, metavar="PATH",
                   help="repository-relative paths the change touches")
    p.add_argument("--rules", metavar="PATH",
                   help="read this rules file instead of governance/review-rules.yml, "
                        "such as the base branch's copy in CI")
    p.set_defaults(func=cmd_policy_review_rules, output_kind="report")
