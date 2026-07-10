## Forward requested version/edition to the site step in `cmk-dev-install-site`
<!--
type: bugfix
scope: all
affected: all
-->

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
