## Find release candidates in suffixed tstbuilds folders
<!--
type: bugfix
scope: all
affected: all
-->

`cmk-dev-install 2.4.0p40-rc1` failed with `Download URL not found.`, because
tstbuilds stores release candidates in folders with a suffix, e.g.
`2.4.0p40-rc1+security/`. The folder is now looked up in the tstbuilds listing,
with or without a suffix. The `-rcN` format is also listed in `--help`.
