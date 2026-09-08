## Fix `cmk-dev-install-site` rejecting options without a build version

<!--
type: bugfix
scope: all
affected: all
-->

`cmk-dev-install-site -n foo` failed with

```
cmk-dev-install: error: argument build-version: 'foo' doesn't match expected format ...
```

Options can now be used without also passing a build version.
