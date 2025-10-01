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

Now `--name` is available to speficy the name of the site created with
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
