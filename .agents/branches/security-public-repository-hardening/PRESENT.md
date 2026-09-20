# Security branch present state

Branch: security/public-repository-hardening
Base: main at a672c56816ecb1df04b3c343f0031942e0224945.
The isolated checkout contains only security changes; no original G4 changes or
local environment files were transferred. Full branch tests: 1890 passed,
25 warnings in 36.85 seconds using Python 3.14 and the patched dependencies.

JavaScript rendering tests: 2 passed. Gitleaks working-tree scan: no leaks found.
Google alert 1: resolved as used_in_tests after HTTP 400 / API_KEY_INVALID.
Secret scanning and push protection remain enabled. No production deployment.
Diff whitespace checks pass. The original working checkout was not committed.
Next action: commit and push only this isolated branch, then inspect PR CI.
