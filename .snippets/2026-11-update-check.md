## Warn when a newer cmk-dev-site is available
<!--
type: feature
scope: all
affected: all
-->

`cmk-dev-install`, `cmk-dev-site` and `cmk-dev-install-site` now tell you when
PyPI has a newer version, at the start and at the end of a run:

```
A new version of cmk-dev-site is available: 1.23.0 (you have 1.20.0).
Update with: pipx upgrade cmk-dev-site
```

The upgrade command matches how the tool was installed (pipx, `uv tool`, `uvx`
or pip). PyPI is asked at most once a day in the background, so the check does not
noticeably slow a command down or make it fail when offline. Set
`CMK_DEV_SITE_NO_UPDATE_CHECK=1` to turn it off.
