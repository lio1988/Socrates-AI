# Security publication plan

1. Completed: isolate the reviewed security patch on current public main.
2. Completed: verify Google alert 1 using the provider's read-only endpoint;
   API_KEY_INVALID confirmed; resolve as used_in_tests, without publishing values.
3. Completed: full tests (1890 passed), JavaScript checks (2 passed) and Gitleaks
   (no leaks found) on this branch.
4. Completed: commit only scoped changes, push this branch and open PR #79 to main.
5. Checked: GitHub reported no check runs yet; local validation is complete.
   Pending: GitHub validation, review and separately authorized merge/deployment.

Do not merge, rewrite history, activate providers or deploy as part of this PR.
