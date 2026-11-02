# Security policy (draft)

Report issues privately to the maintainers. Do not open public issues for
vulnerabilities.

Release checklist: secret scan of the repo, permission check on `.collabai/`,
schema fuzz on `/events`, token-expiry check, and a clean `uninstall --yes`
in a scratch dir before tagging.
