# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!--
## [x.y.z] - yyyy-mm-dd
### Added
### Changed
### Removed
### Fixed
-->
<!--
RegEx for release version from file
r"^\#\# \[\d{1,}[.]\d{1,}[.]\d{1,}\] \- \d{4}\-\d{2}-\d{2}$"
-->

## Released
## [1.22.0] - 2026-10-23T11:13:34+02:00
<!-- meta = {'type': 'feature', 'scope': ['all'], 'affected': ['all']} -->

`cmk-dev-install`, `cmk-dev-site` and `cmk-dev-install-site` now print how long
they took once they are done:

```
$ cmk-dev-install-site 2.5.0
...

Took 2m 05s
```

`cmk-dev-install-site` shows a single total for the installation and the site
setup together. The time is also shown if the command fails or is interrupted
with Ctrl-C. Runs shorter than a second, such as `--help`, stay quiet.

[1.22.0]: https://review.lan.tribe29.com/gitweb?p=checkmk_dev_tools.git;a=tag;h=refs/tags//1.22.0

## [1.21.1] - 2026-10-22T14:42:46+02:00
<!-- meta = {'type': 'bugfix', 'scope': ['all'], 'affected': ['all']} -->

When connecting a remote site (`cmk-dev-install -d 1`), `cmk-dev-site` trusted
the remote site's CA but did not write
`~/var/ssl/remote_sites_cas/<remote>.pem` on the central site, which the GUI
writes when you trust a CA there. Without it, baking agents that register to the
remote site failed, and the data backend reported the remote site's CA as not
trusted. The file is now written as well.

[1.21.1]: https://review.lan.tribe29.com/gitweb?p=checkmk_dev_tools.git;a=tag;h=refs/tags//1.21.1

## [1.21.0] - 2026-10-20T15:25:13+02:00
<!-- meta = {'type': 'feature', 'scope': ['all'], 'affected': ['all']} -->

`cmk-dev-site` now records "trial" as the trial mode selection of every site it
creates, so Checkmk does not ask admins on login whether the site is used as a
trial or with an existing license:

```
$ cmk-dev-site
...
[v300]: Preselected trial mode, so the trial mode selection gate won't show. Show it with --show-trial-mode-selection
```

To be asked anyway, create the site with `--show-trial-mode-selection`:

```
cmk-dev-site --show-trial-mode-selection
```

`cmk-dev-install-site` does not forward this option, so its sites always have
trial mode preselected.

[1.21.0]: https://review.lan.tribe29.com/gitweb?p=checkmk_dev_tools.git;a=tag;h=refs/tags//1.21.0

## [1.20.0] - 2026-09-28T11:28:02+02:00
<!-- meta = {'type': 'feature', 'scope': ['all'], 'affected': ['all']} -->

Newly created sites now get `CMK_DEV=true` in their `etc/environment`, so
they can be recognized as development sites.

[1.20.0]: https://review.lan.tribe29.com/gitweb?p=checkmk_dev_tools.git;a=tag;h=refs/tags//1.20.0

## [1.19.3] - 2026-09-08T16:00:52+02:00
<!-- meta = {'type': 'bugfix', 'scope': ['all'], 'affected': ['all']} -->

`cmk-dev-install-site -n foo` failed with

```
cmk-dev-install: error: argument build-version: 'foo' doesn't match expected format ...
```

Options can now be used without also passing a build version.

[1.19.3]: https://review.lan.tribe29.com/gitweb?p=checkmk_dev_tools.git;a=tag;h=refs/tags//1.19.3

## [1.19.2] - 2026-08-27T14:00:46+02:00
<!-- meta = {'type': 'bugfix', 'scope': ['all'], 'affected': ['all']} -->

Setting up a distributed setup failed with

```
cmk_dev_site.cmk.rest_api.CheckmkAPIException: Failed to create site connection
```

because Checkmk 3.0.0 requires `authentication_connections` in the
`configuration_connection` part of the site connection payload. It is now sent
as `{"type": "disabled"}` for 3.0.0 and newer, matching the `user_sync` setting
next to it. Older versions do not know the field and reject payloads containing
it, so it is omitted there.

[1.19.2]: https://review.lan.tribe29.com/gitweb?p=checkmk_dev_tools.git;a=tag;h=refs/tags//1.19.2

## [1.19.1] - 2026-08-27T14:00:46+02:00
<!-- meta = {'type': 'bugfix', 'scope': ['internal'], 'affected': ['all']} -->

Building the package failed with

```
InvalidDistribution: Invalid distribution metadata: '2.5' is not a valid metadata version
```

`hatchling` 1.32.0 writes `Metadata-Version: 2.5`, but `twine` 6.x refuses
anything above 2.4 from a hard-coded list in its own source, so no `packaging`
update can help. `twine` is now `>=7,<8`, which validates via `packaging`
instead.

The build backend was also unpinned and resolved fresh from PyPI on every CI
run, so the produced artifacts could change without a commit. `uv build` is now
called with `--build-constraints build-constraints.txt`, which pins
`hatchling==1.32.0`. The pin lives in the constraints file rather than in
`[build-system] requires`, because that field ships in the sdist and would
force the exact version on everyone building from source.

[1.19.1]: https://review.lan.tribe29.com/gitweb?p=checkmk_dev_tools.git;a=tag;h=refs/tags//1.19.1

## [1.19.0] - 2026-07-27T23:03:28+02:00
<!-- meta = {'type': 'feature', 'scope': ['all'], 'affected': ['all']} -->

`cmk-dev-site` now sets `MCP_SERVER=on` and `MCP_TRACE_FORWARD=on` when it
creates a site, so Checkmk's MCP server is reachable at
`http://localhost/<site>/check_mk/mcp` without any further setup:

```
$ cmk-dev-site
...
[v300]: Forwarding MCP usage data to Checkmk's telemetry collector (mcp-analytics.checkmk.com). Disable with --omd-configs MCP_TRACE_FORWARD=off
```

Both options are only set where the installed version and edition ship the
corresponding omd hooks (Checkmk 3.0.0 and newer, every edition except
community). Older versions and community sites are left untouched.

`MCP_TRACE_FORWARD` forwards the MCP server's OpenTelemetry traces (which tools
were called, response times and sizes, error codes, which AI client was used,
and a random session ID, but never request or result content) to Checkmk's
central telemetry collector.

Opt out of either with `--omd-configs`:

```
cmk-dev-site --omd-configs MCP_SERVER=off
cmk-dev-site --omd-configs MCP_TRACE_FORWARD=off
```

[1.19.0]: https://review.lan.tribe29.com/gitweb?p=checkmk_dev_tools.git;a=tag;h=refs/tags//1.19.0

## [1.18.0] - 2026-07-21T10:23:47+02:00
<!-- meta = {'type': 'feature', 'scope': ['internal'], 'affected': ['all']} -->

Building a version from git (`cmk-dev-install <branch>:<commit>`) previously
spawned `cmk_dev.ci_artifacts` as a subprocess with captured output, so there
was no feedback at all while Jenkins looked for or ran a build — often for
many minutes.

`checkmk-dev-tools` 2.3.0 exposes `fetch_artifacts()` as a public API, so the
dependency is bumped to `>=2.3.0` and the function is now imported and called
directly. Its log output is routed through the same stderr handler as the
rest of cmk-dev-install, so build lookup, trigger, wait, and download progress
is now visible live and honors `-v`/`-q`.

[1.18.0]: https://review.lan.tribe29.com/gitweb?p=checkmk_dev_tools.git;a=tag;h=refs/tags//1.18.0

## [1.17.5] - 2026-07-21T10:23:47+02:00
<!-- meta = {'type': 'bugfix', 'scope': ['internal'], 'affected': ['all']} -->

Installing a release candidate from test.pypi.org could fail because the
unpinned `fastapi` dependency resolved to a junk `FASTAPI 1.0` squatter
package hosted there, whose broken sdist fails to build
(`FileNotFoundError: DESCRIPTION.txt`).

`fastapi` is now constrained to `>=0.115,<1`, so this specific squatter is
excluded from resolution. This only fixes the fastapi build failure: mixing
`-i https://test.pypi.org/simple/` with `--extra-index-url
https://pypi.org/simple` still lets any *other* dependency be shadowed by a
higher-versioned package on test.pypi.org (a dependency-confusion risk, since
anyone can publish any package name there). Fetch only our own package from
test.pypi.org and resolve every dependency from pypi.org alone instead:

```
pip download --no-cache-dir --no-deps -d /tmp/rc-wheel \
    -i https://test.pypi.org/simple/ cmk-dev-site==<VERSION_WITH_RC>
pip install --no-cache-dir --force-reinstall /tmp/rc-wheel/cmk_dev_site-*.whl
```

[1.17.5]: https://review.lan.tribe29.com/gitweb?p=checkmk_dev_tools.git;a=tag;h=refs/tags//1.17.5

## [1.17.4] - 2026-07-20T10:38:51+02:00
<!-- meta = {'type': 'bugfix', 'scope': ['all'], 'affected': ['all']} -->

`cmk-dev-install-site` forwarded the version exactly as the user typed it to
`cmk-dev-site`, so a partial version stopped at the interactive version
selection:

```
$ cmk-dev-install-site 2.3
cmk-dev-install 2.3 && cmk-dev-site 2.3 -f
...
Available versions:
        1 2.3.0-2026.07.10.cee
        ...
Choose an option:
```

The site step now uses the version resolved by `cmk-dev-install` (e.g. `2.3`
resolves to `2.3.0-2026.07.10.cee`, edition included), so partial versions,
`X.Y.Z-daily`, and omitted versions all work non-interactively and the site is
always created on the version that was just installed.

[1.17.4]: https://review.lan.tribe29.com/gitweb?p=checkmk_dev_tools.git;a=tag;h=refs/tags//1.17.4

## [1.17.3] - 2026-07-13T17:09:42+02:00
<!-- meta = {'type': 'bugfix', 'scope': ['all'], 'affected': ['all']} -->

`cmk-dev-site` failed on the community edition when creating the site host:
the REST API rejected the `bake_agent` query parameter with "The bake_agent
field is not supported by this license", even though it was set to `False`.
The parameter is no longer sent at all — `False` is the API default, so
behavior is unchanged on editions that support the agent bakery, and host
creation now works on editions without it (e.g. community).

[1.17.3]: https://review.lan.tribe29.com/gitweb?p=checkmk_dev_tools.git;a=tag;h=refs/tags//1.17.3

## [1.17.2] - 2026-07-10T09:42:03+02:00
<!-- meta = {'type': 'bugfix', 'scope': ['all'], 'affected': ['all']} -->

`cmk-dev-install-site <build-version> <edition>` installed the requested OMD
version but then set up the site on the system's default OMD version
(`omd version -b`), e.g.:

```
$ cmk-dev-install-site 3.0.0-2026-06-29 ultimate
...
INFO: Validate installation of 2.5.0-2026.06.24.ultimate...OK
```

The requested version and edition are now forwarded to `cmk-dev-site` as the
combined positional (e.g. `3.0.0-2026-06-29.ultimate`), so the site is created
on the version that was just installed instead of depending on the system
default OMD version.

[1.17.2]: https://review.lan.tribe29.com/gitweb?p=checkmk_dev_tools.git;a=tag;h=refs/tags//1.17.2

## [1.17.1] - 2026-06-29T07:07:11+02:00
<!-- meta = {'type': 'bugfix', 'scope': ['internal'], 'affected': ['all']} -->

`cmk-dev-install` now invokes `cmk_dev.ci_artifacts` via `sys.executable -m`
instead of looking up `ci-artifacts` on `PATH`. When `cmk-dev-site` is installed
as a `uv tool` or `pipx` app, dependency scripts are not added to `PATH`, causing
git-based builds to fail. Using the current interpreter avoids that entirely.

[1.17.1]: https://review.lan.tribe29.com/gitweb?p=checkmk_dev_tools.git;a=tag;h=refs/tags//1.17.1

## [1.17.0] - 2026-06-15T08:34:00+02:00
<!-- meta = {'type': 'feature', 'scope': ['all'], 'affected': ['all']} -->

There is no 2.6 release: the version after 2.5.0 is 3.0.0. Requesting a 2.6
version (e.g. `cmk-dev-install 2.6` or `2.6.0`) is now transparently redirected
to the matching 3.0 version. Edition handling was also adjusted so that 3.x uses
the new edition specifiers introduced with 2.5.0 instead of failing.

[1.17.0]: https://review.lan.tribe29.com/gitweb?p=checkmk_dev_tools.git;a=tag;h=refs/tags//1.17.0

## [1.16.0] - 2026-06-01T21:08:39+02:00
<!-- meta = {'type': 'feature', 'scope': ['all'], 'affected': ['all']} -->

`cmk-dev-install` now accepts `-p`/`--path` to install a local `.deb` file
instead of downloading one. The OMD version is derived from the file name and
ACLs are applied just like for a downloaded package.

[1.16.0]: https://review.lan.tribe29.com/gitweb?p=checkmk_dev_tools.git;a=tag;h=refs/tags//1.16.0

## [1.15.2] - 2026-04-20T16:21:14+02:00
<!-- meta = {'type': 'bugfix', 'scope': ['all'], 'affected': ['all']} -->

It was not possible to build from git for 2.3.0 and 2.4.0 because the internal
jenkin job names changed from 2.4.0 to 2.5.0, and before this change we only
supported building from git for 2.5.0 and master.

[1.15.2]: https://review.lan.tribe29.com/gitweb?p=checkmk_dev_tools.git;a=tag;h=refs/tags//1.15.2

## [1.15.1] - 2026-03-31T16:37:35+02:00
<!-- meta = {'type': 'bugfix', 'scope': ['all'], 'affected': ['all']} -->

`cmk-dev-install` now warns and skips ACL setup if `setfacl` is not available,
instead of failing with a cryptic error. The warning includes instructions to
install the `acl` package and reinstall the version to apply ACLs properly.

[1.15.1]: https://review.lan.tribe29.com/gitweb?p=checkmk_dev_tools.git;a=tag;h=refs/tags//1.15.1

## [1.15.0] - 2026-03-20T10:42:12+01:00
<!-- meta = {'type': 'feature', 'scope': ['all'], 'affected': ['cloud']} -->

Added otel configuration for cloud edition

[1.15.0]: https://review.lan.tribe29.com/gitweb?p=checkmk_dev_tools.git;a=tag;h=refs/tags//1.15.0

## [1.14.2] - 2026-03-16T15:30:47+01:00
<!-- meta = {'type': 'bugfix', 'scope': ['all'], 'affected': ['all']} -->

The `--help` output for `cmk-dev-install` and `cmk-dev-site` was confusing in two ways:

- The positional argument was displayed as `version`, clashing with the `--version` flag.
  It now shows as `build-version` (`cmk-dev-install`) and `omd-version` (`cmk-dev-site`) to make the distinction clear.
- The date format for daily builds was only shown as a concrete example (e.g. `2.4.0-2025-01-01`),
  leaving the field order ambiguous. The help text now shows the format pattern (`YYYY-MM-DD` / `YYYY.MM.DD`) alongside the example.

[1.14.2]: https://review.lan.tribe29.com/gitweb?p=checkmk_dev_tools.git;a=tag;h=refs/tags//1.14.2

## [1.14.1] - 2026-03-11T09:04:54+01:00
<!-- meta = {'type': 'bugfix', 'scope': ['all'], 'affected': ['all']} -->

Release candidate packages are in tstbuilds, but not in the official release repository.
This caused the `cmk-dev-install` command to fail when trying to install a release candidate version.
This is now fixed by only looking for release candidates in the testbuilds repository if release candidate version is specified.

[1.14.1]: https://review.lan.tribe29.com/gitweb?p=checkmk_dev_tools.git;a=tag;h=refs/tags//1.14.1

## [1.14.0] - 2026-03-10T12:24:23+01:00
<!-- meta = {'type': 'feature', 'scope': ['all'], 'affected': ['cloud']} -->

Added an interactive login form to the mock OIDC service for local testing with different usernames and roles.

The `/authorize` endpoint now displays a plain HTML form with a username field (pre-filled with `test@test.com`) and radio buttons for `user` or `admin` role selection. The selected identity is carried through the OAuth flow and included in the issued JWT tokens.

[1.14.0]: https://review.lan.tribe29.com/gitweb?p=checkmk_dev_tools.git;a=tag;h=refs/tags//1.14.0

## [1.13.0] - 2026-02-26T21:30:52+01:00
<!-- meta = {'type': 'feature', 'scope': ['all'], 'affected': ['all']} -->

When using `cmk-dev-install` it will look if there is an existing matching deb
for the requested version. If one is found the download is skipped.

[1.13.0]: https://review.lan.tribe29.com/gitweb?p=checkmk_dev_tools.git;a=tag;h=refs/tags//1.13.0

## [1.12.2] - 2026-01-21T18:02:27+01:00
<!-- meta = {'type': 'bugfix', 'scope': ['all'], 'affected': ['all']} -->

Previously the customer was only added for OLD_MANAGED Edition, with new edition this should have been also
considered for ULTIMATEMT which caused error in api call.

[1.12.2]: https://review.lan.tribe29.com/gitweb?p=checkmk_dev_tools.git;a=tag;h=refs/tags//1.12.2

## [1.12.1] - 2026-01-21T18:02:27+01:00
<!-- meta = {'type': 'bugfix', 'scope': ['all'], 'affected': ['all']} -->

Previously if there was an error in the API call, the status code and response were not printed in the exception.
Now, the status code and response will be included in the API exception message for better debugging.

[1.12.1]: https://review.lan.tribe29.com/gitweb?p=checkmk_dev_tools.git;a=tag;h=refs/tags//1.12.1

## [1.12.0] - 2026-01-15T14:17:33+01:00
<!-- meta = {'type': 'feature', 'scope': ['all'], 'affected': ['all']} -->

TBD

[1.12.0]: https://review.lan.tribe29.com/gitweb?p=checkmk_dev_tools.git;a=tag;h=refs/tags//1.12.0

## [1.11.1] - 2025-12-16T14:44:10+01:00
<!-- meta = {'type': 'bugfix', 'scope': ['all'], 'affected': ['all']} -->

Creating a site with `cmk-dev-install-site 2.4.0` failed with an error:

```
ERROR: Checkmk 2.4.0p0 is not installed.
```

[1.11.1]: https://review.lan.tribe29.com/gitweb?p=checkmk_dev_tools.git;a=tag;h=refs/tags//1.11.1

## [1.11.0] - 2025-11-13T10:01:42+01:00
<!-- meta = {'type': 'feature', 'scope': ['external'], 'affected': ['all']} -->

TBD

[1.11.0]: https://review.lan.tribe29.com/gitweb?p=checkmk_dev_tools.git;a=tag;h=refs/tags//1.11.0

## [1.10.1] - 2025-11-13T10:01:42+01:00
<!-- meta = {'type': 'bugfix', 'scope': ['all'], 'affected': ['all']} -->

Removal of packages in cmk-dev-install occasionally resulted in errors due to f12 in the site.
Now we check if the package exists and remove the package without silenting the raising error to ensure we get the correct error at the end.
Additionally, the package directory is removed before the package removal to resolve the aforementioned issue.

[1.10.1]: https://review.lan.tribe29.com/gitweb?p=checkmk_dev_tools.git;a=tag;h=refs/tags//1.10.1

## [1.10.0] - 2025-11-13T10:01:42+01:00
<!-- meta = {'type': 'feature', 'scope': ['internal'], 'affected': ['all']} -->

Prefer downloading packages from the public downloads.checkmk.com server, instead of the internal tsbuilds server.
We only use tstbuilds-artifacts.lan.tribe29.com for the cloud edition.

[1.10.0]: https://review.lan.tribe29.com/gitweb?p=checkmk_dev_tools.git;a=tag;h=refs/tags//1.10.0

## [1.9.1] - 2025-11-12T11:34:25+01:00
<!-- meta = {'type': 'bugfix', 'scope': ['internal'], 'affected': ['all']} -->

fix pyproject toml file. this made the last release fail.

also fix typing problem which was caused by a not rebased merge

[1.9.1]: https://review.lan.tribe29.com/gitweb?p=checkmk_dev_tools.git;a=tag;h=refs/tags//1.9.1

## [1.9.0] - 2025-11-11T10:39:13+01:00
<!-- meta = {'type': 'feature', 'scope': ['all'], 'affected': ['all']} -->

Added a fake OIDC provider to enable local development and testing of CSE sites without requiring external authentication services.
The mock authentication service implements all required OIDC endpoints and supports tenant-based authorization.

**Key additions:**
- New `mock-auth` command to start the fake OIDC provider on port 10080
- Automatic generation of CSE configuration files (`/etc/cse/cognito-cmk.json` and `/etc/cse/admin_panel_url.json`)
- Port availability check when creating CSE sites to ensure mock-auth is running
- Complete OIDC flow implementation including token generation, JWKS endpoints, and authorization
- Fixed tenant ID for consistent testing (`092fd467-0d2f-4e0a-90b8-4ee6494f7453`)

To use: Run `mock-auth` before creating CSE sites with `cmk-dev-site`.

[1.9.0]: https://review.lan.tribe29.com/gitweb?p=checkmk_dev_tools.git;a=tag;h=refs/tags//1.9.0

## [1.8.0] - 2025-11-10T17:25:50+01:00
<!-- meta = {'type': 'feature', 'scope': ['internal'], 'affected': ['all']} -->

With this change you can run unittests locally using `uv run pytest`.
Also the CI will execute them.

[1.8.0]: https://review.lan.tribe29.com/gitweb?p=checkmk_dev_tools.git;a=tag;h=refs/tags//1.8.0

## [1.7.0] - 2025-11-05T16:57:08+01:00
<!-- meta = {'type': 'feature', 'scope': ['all'], 'affected': ['all']} -->

for 2.5 and upwards you have to use the new edition names,
for 2.4 and before you can still use the old edition names.

[1.7.0]: https://review.lan.tribe29.com/gitweb?p=checkmk_dev_tools.git;a=tag;h=refs/tags//1.7.0

## [1.6.5] - 2025-11-04T10:36:14+01:00
<!-- meta = {'type': 'bugfix', 'scope': ['internal'], 'affected': ['all']} -->

stop using legacy hook name

[1.6.5]: https://review.lan.tribe29.com/gitweb?p=checkmk_dev_tools.git;a=tag;h=refs/tags//1.6.5

## [1.6.4] - 2025-11-04T08:27:42+01:00
<!-- meta = {'type': 'bugfix', 'scope': ['internal'], 'affected': ['all']} -->

update all dependencies

[1.6.4]: https://review.lan.tribe29.com/gitweb?p=checkmk_dev_tools.git;a=tag;h=refs/tags//1.6.4

## [1.6.3] - 2025-11-04T08:27:42+01:00
<!-- meta = {'type': 'bugfix', 'scope': ['external'], 'affected': ['all']} -->

Tracing is not supported on all editions (not the CSE). In case we cannot setup tracing during
site creation just print a warning and leave tracing unconfigured.

[1.6.3]: https://review.lan.tribe29.com/gitweb?p=checkmk_dev_tools.git;a=tag;h=refs/tags//1.6.3

## [1.6.2] - 2025-10-30T08:46:48+01:00
<!-- meta = {'type': 'bugfix', 'scope': ['all'], 'affected': ['all']} -->

previously you may have seen:
```
cmk_dev_site.cmk.rest_api.CheckmkAPIException: Failed to create site connection
```

this is now fixed.

[1.6.2]: https://review.lan.tribe29.com/gitweb?p=checkmk_dev_tools.git;a=tag;h=refs/tags//1.6.2

## [1.6.1] - 2025-10-22T18:20:50+02:00
<!-- meta = {'type': 'bugfix', 'scope': ['all'], 'affected': ['all']} -->

Using the partial version without a VPN results in long wait times when searching for TSBUILDS, as the URL is inaccessible.
This change omits the TSBUILDS URL from the search, improving performance for users without a VPN.

[1.6.1]: https://review.lan.tribe29.com/gitweb?p=checkmk_dev_tools.git;a=tag;h=refs/tags//1.6.1

## [1.6.0] - 2025-10-22T11:29:28+02:00
<!-- meta = {'type': 'feature', 'scope': ['all'], 'affected': ['all']} -->
The logging decorator now includes an optional flag to print the output of functions.
Additionally, the `url_exist` message has been removed to prevent unnecessary information from being displayed.

[1.6.0]: https://review.lan.tribe29.com/gitweb?p=checkmk_dev_tools.git;a=tag;h=refs/tags//1.6.0

## [1.5.0] - 2025-10-22T11:12:49+02:00
<!-- meta = {'type': 'feature', 'scope': ['all'], 'affected': ['all']} -->

cmk-dev-install (or cmk-dev-site-install) now support `2.M.0{pP|bB}-rcN` as version input.
`N` stands for the release candidate number.

[1.5.0]: https://review.lan.tribe29.com/gitweb?p=checkmk_dev_tools.git;a=tag;h=refs/tags//1.5.0

## [1.4.2] - 2025-10-14T08:35:51+02:00
<!-- meta = {'type': 'bugfix', 'scope': ['all'], 'affected': ['all']} -->

Correct path to Jenkins job providing the package artifact. With CMK-26121 the build package job was split into pre-build, build and sign. This change sets the overall `trigger-cmk-distro-package` as job instead of the `trigger-cmk-distro-package` which would allocate resources longer due to the waittime for the pre-build part. Additionally the package would not be signed.

[1.4.2]: https://review.lan.tribe29.com/gitweb?p=checkmk_dev_tools.git;a=tag;h=refs/tags//1.4.2

## [1.4.1] - 2025-09-24T13:15:08+02:00
<!-- meta = {'type': 'bugfix', 'scope': ['all'], 'affected': ['all']} -->

Appended a trailing slash so no HTTP-redirect takes place.

[1.4.1]: https://review.lan.tribe29.com/gitweb?p=checkmk_dev_tools.git;a=tag;h=refs/tags//1.4.1

## [1.4.0] - 2025-09-24T13:15:08+02:00
<!-- meta = {'type': 'feature', 'scope': ['all'], 'affected': ['all']} -->

It's now possible to use `-vvvv` and `-vvvvv` to get verbose http request
logging.

[1.4.0]: https://review.lan.tribe29.com/gitweb?p=checkmk_dev_tools.git;a=tag;h=refs/tags//1.4.0

## [1.3.0] - 2025-09-24T13:13:47+02:00
<!-- meta = {'type': 'feature', 'scope': ['all'], 'affected': ['all']} -->

The shown rate is for the overall download, so it stabilizes over time.

[1.3.0]: https://review.lan.tribe29.com/gitweb?p=checkmk_dev_tools.git;a=tag;h=refs/tags//1.3.0

## [1.2.1] - 2025-09-09T08:19:44+02:00
<!-- meta = {'type': 'bugfix', 'scope': ['all'], 'affected': ['all']} -->

This resolves the problem of working without a vpn by introducing faster test for checking vpn.
Additionally, the bug for resolving package hash on tstbuilds server has resolved.

[1.2.1]: https://review.lan.tribe29.com/gitweb?p=checkmk_dev_tools.git;a=tag;h=refs/tags//1.2.1

## [1.2.0] - 2025-08-26T17:37:14+02:00
<!-- meta = {'type': 'feature', 'scope': ['all'], 'affected': ['all']} -->

User can use `--omd-config` to add list of key-value for OMD config.

[1.2.0]: https://review.lan.tribe29.com/gitweb?p=checkmk_dev_tools.git;a=tag;h=refs/tags//1.2.0

## [1.1.1] - 2025-08-25T11:58:43+02:00
<!-- meta = {'type': 'bugfix', 'scope': ['all'], 'affected': ['all']} -->

remove the mandatory `-f` for `cmk-dev-install` when using
`cmk-dev-install-site`

[1.1.1]: https://review.lan.tribe29.com/gitweb?p=checkmk_dev_tools.git;a=tag;h=refs/tags//1.1.1

## [1.1.0] - 2025-08-18T18:46:19+02:00
<!-- meta = {'type': 'feature', 'scope': ['all'], 'affected': ['all']} -->

The log output is more concise and now includes the site link.

[1.1.0]: https://review.lan.tribe29.com/gitweb?p=checkmk_dev_tools.git;a=tag;h=refs/tags//1.1.0

## [1.0.0] - 2025-08-18T14:43:43+02:00
<!-- meta = {'type': 'breaking', 'scope': ['all'], 'affected': ['all']} -->

We hope to restore `cmk-dev` in the future but have to coordinate
internally, which takes some time.

[1.0.0]: https://review.lan.tribe29.com/gitweb?p=checkmk_dev_tools.git;a=tag;h=refs/tags//1.0.0

## [0.4.1] - 2025-08-18T12:36:24+02:00
<!-- meta = {'type': 'bugfix', 'scope': ['all'], 'affected': ['all']} -->

previously the following error was visible when executed without sub command.

```
AttributeError: 'Namespace' object has no attribute 'func'
```

now the help is printed

[0.4.1]: https://review.lan.tribe29.com/gitweb?p=checkmk_dev_tools.git;a=tag;h=refs/tags//0.4.1

## [0.4.0] - 2025-08-18T08:21:29+02:00
<!-- meta = {'type': 'feature', 'scope': ['all'], 'affected': ['all']} -->

Now `--name` is available to specify the name of the site created with
`cmk-dev site-install`.

[0.4.0]: https://review.lan.tribe29.com/gitweb?p=checkmk_dev_tools.git;a=tag;h=refs/tags//0.4.0

## [0.3.0] - 2025-08-14T08:52:11+02:00
<!-- meta = {'type': 'feature', 'scope': ['all'], 'affected': ['all']} -->

`cmk-dev install-site` and its alias `cmk-dev is` is a shortcut wrapper around
`cmk-dev install` and `cmk-dev site`. It can be used to install the version and
create a site with one simple command.

This also introduce the `cmk-dev` command which has currently three
subcommands: `site`, `install`, `install-site`.

[0.3.0]: https://review.lan.tribe29.com/gitweb?p=checkmk_dev_tools.git;a=tag;h=refs/tags//0.3.0

## [0.2.5] - 2025-08-11T10:21:04+02:00
<!-- meta = {'type': 'bugfix', 'scope': ['all'], 'affected': ['all']} -->

The `run_command` function is now wrapped by the caller module to automatically log both stdout and stderr for each command when debug logging is enabled via `-v`.

[0.2.5]: https://review.lan.tribe29.com/gitweb?p=checkmk_dev_tools.git;a=tag;h=refs/tags//0.2.5

## [0.2.4] - 2025-08-05T15:08:29+02:00
<!-- meta = {'type': 'bugfix', 'scope': ['internal'], 'affected': ['all']} -->

inline documentation instead

[0.2.4]: https://review.lan.tribe29.com/gitweb?p=checkmk_dev_tools.git;a=tag;h=refs/tags//0.2.4

## [0.2.3] - 2025-08-04T15:42:43+02:00
<!-- meta = {'type': 'bugfix', 'scope': ['internal'], 'affected': ['all']} -->

netstat is deprecated, fresh installs do not have netstat

[0.2.3]: https://review.lan.tribe29.com/gitweb?p=checkmk_dev_tools.git;a=tag;h=refs/tags//0.2.3

## [0.2.2] - 2025-08-04T15:42:37+02:00
<!-- meta = {'type': 'bugfix', 'scope': ['internal'], 'affected': ['all']} -->

failed in core logic

[0.2.2]: https://review.lan.tribe29.com/gitweb?p=checkmk_dev_tools.git;a=tag;h=refs/tags//0.2.2

## [0.2.1] - 2025-07-31T14:24:35+02:00
<!-- meta = {'type': 'bugfix', 'scope': ['internal'], 'affected': ['all']} -->

Moved toplevel python modules into cmk_dev_site module.

This fixes

```
ModuleNotFoundError: No module named 'cmk'
```

[0.2.1]: https://review.lan.tribe29.com/gitweb?p=checkmk_dev_tools.git;a=tag;h=refs/tags//0.2.1

## [0.2.0] - 2025-07-31T12:58:49+02:00
<!-- meta = {'type': 'feature', 'scope': ['internal'], 'affected': ['all']} -->

New modules for `rest_api`, omd version, and logging has been created to increase reuse.

[0.2.0]: https://review.lan.tribe29.com/gitweb?p=checkmk_dev_tools.git;a=tag;h=refs/tags//0.2.0

## [0.1.0] - 2025-07-15T10:40:06+02:00
<!-- meta = {'type': 'feature', 'scope': ['all'], 'affected': ['all']} -->

Make `cmk-dev-site` package public

[0.1.0]: https://review.lan.tribe29.com/gitweb?p=checkmk_dev_tools.git;a=tag;h=refs/tags//0.1.0

## [0.0.0] - 2025-07-14
### Added
- Make `cmk-dev-site` public

[0.0.0]: https://review.lan.tribe29.com/gitweb?p=cmk-dev-site.git;a=tag;h=refs/tags/0.0.0
