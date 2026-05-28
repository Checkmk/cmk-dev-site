## Install a local deb file with `-p`/`--path`
<!--
type: feature
scope: all
affected: all
-->

`cmk-dev-install` now accepts `-p`/`--path` to install a local `.deb` file
instead of downloading one. The OMD version is derived from the file name and
ACLs are applied just like for a downloaded package.
