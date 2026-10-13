# adding-a-kind-classifies-as-equivalent

## Decided by

jed72

## Date

2026-10-12

## Supersedes

Nothing.

## Decision

A configuration layer that only adds an artifact kind classifies as `equivalent` and needs no waiver. The classifier keeps its four results (`equivalent`, `tightening`, `loosening` and `incomparable`). A fifth result is not added.

`compass policy diff` names the added kind on a line of its own, outside the classification: `adds artifact kind <id>`. A layer that adds a kind and also makes an approach owe it classifies as `tightening`. A layer that removes a kind an approach owes classifies as `loosening`. A layer that changes the `required_when` of a kind an approach owes classifies as `incomparable`.

## Why

A kind that no approach owes changes nothing an issue must do, so there is nothing to loosen or tighten. A fifth result would change the classifier's JSON shape, its cache key and every consumer of `result`, for a case the existing four describe correctly.

## Evidence

The requirements review of the issue `artifact-catalogue-fields` (question 10 and the maintainer's answer M1, accepted on 2026-10-12). `tests/test_artifact_catalogue_fields.py::test_acf_33` holds the four cases.
