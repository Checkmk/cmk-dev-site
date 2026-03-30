## Auto-install acl package if setfacl is missing
<!--
type: bugfix
scope: all
affected: all
-->

`cmk-dev-install` now automatically installs the `acl` package if `setfacl`
is not available on the system, instead of failing with a cryptic error.
