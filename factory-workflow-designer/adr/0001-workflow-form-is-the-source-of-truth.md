# The Workflow Form is the source of truth; generated Markdown is not parsed back

The designer saves each Workflow as a Workflow Form and generates the Bundle from it. It never reads a Bundle back. The reference engine, an existing workflow engine that generates Python, parses its generated code back, because a modeller can edit Python by hand inside a strict grammar. Prose prompts have no such grammar, so a parser would be fragile. Text that the Author must write by hand, such as a Handoff's spec or the Coordinator's rules, goes into named free-text fields of the Workflow Form instead.
