---
name: verify
description: Record that the owner has reviewed a wiki page, after showing any unresolved evidence suspects. Use when the owner says they verified, reviewed, checked or signed off a page, or asks to mark a page as verified.
argument-hint: "<page title or path>"
---

# Verify a page

Record a human review in the page's `verified` list. This is the only path by which `verified` changes from inside Claude Code: the write guard denies every other edit to that field. Scripts live in `${CLAUDE_PLUGIN_ROOT}/scripts/`.

## Steps

1. **Vault check and page.** `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/vault.py detect --json`. Resolve `$ARGUMENTS` to a page under `wiki/` (a title matches the file `wiki/**/<Title>.md`). Stop if it is not a wiki page.

2. **Evidence first.** `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/evidence.py check <page> --json`. If it lists suspects or errors, show them and ask whether to proceed anyway; without an explicit yes, stop here. A review means the owner read the page against its sources.

3. **Who.** `human_id` from `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/vault.py settings --json`; if empty, `git config user.name` lower-cased with dashes.

4. **Record.**

   ```
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/verify.py <page> --by <human_id>
   ```

   The script appends `{by: human:<id>, at: today}` and changes nothing else.

5. **Log and commit.**

   ```
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/log.py append --op verify --title "<page title>"
   git add -A -- . && git commit -m "verify: <page title>"
   ```

6. **Confirm** in one line: page, verifier, date. Mention that lint will flag the page as "review outdated" once its knowledge changes again.
