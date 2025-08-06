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
