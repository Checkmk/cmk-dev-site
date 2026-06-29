## Fix `ci-artifacts` not found when installed via `uv tool` or `pipx`
<!--
type: bugfix
scope: internal
affected: all
-->

`cmk-dev-install` now invokes `cmk_dev.ci_artifacts` via `sys.executable -m`
instead of looking up `ci-artifacts` on `PATH`. When `cmk-dev-site` is installed
as a `uv tool` or `pipx` app, dependency scripts are not added to `PATH`, causing
git-based builds to fail. Using the current interpreter avoids that entirely.
