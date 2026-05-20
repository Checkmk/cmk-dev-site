## Resolve ci-artifacts from venv instead of PATH
<!--
type: bugfix
scope: all
affected: all
-->

`cmk-dev-install` now resolves the `ci-artifacts` binary relative to its own
Python interpreter instead of relying on the system `PATH`. Since `checkmk-dev-tools`
is a declared dependency, `ci-artifacts` is always installed in the same virtual
environment, so the old PATH-based lookup and the related "not found" error message
have been removed.
