---
name: verify
description: Record that you, the owner, have reviewed a wiki page, after seeing any unresolved evidence suspects.
disable-model-invocation: true
argument-hint: "<page title or path>"
---

# Verify a page

Record a human review in the page's `verified` list. Only the owner invokes this skill; the file-tool guard denies every other edit to `verified`, so "human-reviewed" keeps meaning a human reviewed it. Scripts live in `${CLAUDE_PLUGIN_ROOT}/scripts/`.

## Steps

1. **Vault check and page.** `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/vault.py detect --json`; keep `root`. Resolve `$ARGUMENTS` to a page under `wiki/` (a title matches the file `wiki/**/<Title>.md`). Stop if it is not a wiki page.

2. **Evidence first.** `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/evidence.py check <page> --json`. If it lists suspects or errors, show them and ask whether to proceed anyway; without an explicit yes, stop here. A review means the owner read the page against its sources.

3. **Who.** `human_id` from `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/vault.py settings --json`; if it is absent or the placeholder `owner`, use `git config user.name` lower-cased with dashes.

4. **Record.**

   ```
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/verify.py <page> --by <human_id>
   ```

   The script appends `{by: human:<id>, at: today}` and changes nothing else.

5. **Log and commit.**

   ```
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/log.py append --op verify --title "<page title>" --updated "<page title>"
   git -C <root> add -A -- . && git -C <root> commit -m "verify: <page title>"
   ```

6. **Confirm** in one line: page, verifier, date. Mention that lint will flag the page as "review outdated" once its knowledge changes again.
