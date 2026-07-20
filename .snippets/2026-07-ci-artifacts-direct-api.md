## Use the ci-artifacts Python API directly for git builds
<!--
type: feature
scope: internal
affected: all
-->

Building a version from git (`cmk-dev-install <branch>:<commit>`) previously
spawned `cmk_dev.ci_artifacts` as a subprocess with captured output, so there
was no feedback at all while Jenkins looked for or ran a build — often for
many minutes.

`checkmk-dev-tools` 2.3.0 exposes `fetch_artifacts()` as a public API, so the
dependency is bumped to `>=2.3.0` and the function is now imported and called
directly. Its log output is routed through the same stderr handler as the
rest of cmk-dev-install, so build lookup, trigger, wait, and download progress
is now visible live and honors `-v`/`-q`.
