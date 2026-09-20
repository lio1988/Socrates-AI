# Branch: security/public-repository-hardening

Purpose: publish only the reviewed HTTP application security fixes against main.

Read [PRESENT.md](PRESENT.md), [MEMORY.md](MEMORY.md), [PLANS.md](PLANS.md), then
[SECURITY.md](../../../SECURITY.md). Success means offline tests and secret scans
pass on the isolated branch, with no credentials or unrelated G4 changes.

Scope: API access, browser rendering, safe provider errors/timeouts, resource
limits, dependency minimums and security CI. No CED governance changes, provider
activation, history rewrite or production deployment.
