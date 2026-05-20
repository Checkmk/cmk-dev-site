## Stream ci-artifacts logs during git build
<!--
type: bugfix
scope: all
affected: all
-->

When installing a Checkmk version built from git, `cmk-dev-install` now streams
the `ci-artifacts` log output directly to the terminal. Previously, all output was
captured silently, leaving users with no feedback during the potentially long wait
for a Jenkins build to complete.
