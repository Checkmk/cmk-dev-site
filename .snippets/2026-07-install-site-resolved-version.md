## Use the resolved version for the site step in `cmk-dev-install-site`
<!--
type: bugfix
scope: all
affected: all
-->

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
