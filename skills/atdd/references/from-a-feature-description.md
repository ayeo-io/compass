# From a feature description to the four layers

Use these steps when you have a description of a feature but no scenarios yet. They produce everything stage 1 needs.

1. **List the behaviors.** Write down each outcome the description says a user or client can observe. Then list the failure modes the description implies. At refine, settle each one with the person as a scenario, or descope it with `compass scenario descope`.
2. **Write one scenario per behavior.** Use Given, When and Then, in the words the domain already uses. Leave out endpoints, status codes, selectors and storage. The first Given creates the actor's own account, workspace or tenant, for example "Given the user has an account".
3. **Write the DSL.** Give each scenario line one DSL method, grouped by domain part, such as `dsl.user` and `dsl.order`. Name set-up methods `hasX`, actions with a business verb such as `archive`, and checks `confirmX`. For each parameter, note whether it is an aliased identifier or a value with a default.
4. **Write the driver interface.** Give it the same method names as the DSL. Note which drivers the feature needs: API, web, CLI or several.
5. **Stop for review.** This is the end of stage 1, and the refine checkpoint reviews it with the questions in `stage-reviews.md`. Show the person the scenarios, the DSL, the driver interface and the descoped failure modes. Do not implement the driver until they accept them.
