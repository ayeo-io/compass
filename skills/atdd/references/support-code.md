# Support code to have first

Stage 1 needs the following. If any of it is missing, build it first or ask the person how to proceed. The check `acceptance-support-present` names the missing pieces when the project lists their paths under `project.acceptance_support` in `compass.yml`.

- The alias helper described in `skills/atdd/references/isolation.md`, plus helpers for defaults, for example `alias`, `optional` and `optionalList`.
- The driver interface and a factory that picks a driver at start-up, importing the driver where the runner can report a missing one.
- A DSL root that groups the domain parts, such as `dsl.user` and `dsl.todo`.
- A layering test, owned by the project, that fails when the DSL makes a check or a specification line is more than one DSL call.
