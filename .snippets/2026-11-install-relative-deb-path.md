## Install a .deb given by a relative path
<!--
type: bugfix
scope: all
affected: all
-->

`cmk-dev-install -p ./check-mk-enterprise-2.4.0p40_0.noble_amd64.deb` failed
with `E: Unable to locate package`, because the leading `./` was dropped and
`apt-get` read the file name as a package name. The path is now made absolute
before it is passed to `apt-get`.
