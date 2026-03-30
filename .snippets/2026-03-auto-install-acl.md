## Warn when acl package is missing instead of failing
<!--
type: bugfix
scope: all
affected: all
-->

`cmk-dev-install` now warns and skips ACL setup if `setfacl` is not available,
instead of failing with a cryptic error. The warning includes instructions to
install the `acl` package and reinstall the version to apply ACLs properly.
