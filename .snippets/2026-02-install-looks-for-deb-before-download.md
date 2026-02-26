## Re-use existing deb on download
<!--
type: feature
scope: all
affected: all
-->

When using `cmk-dev-install` it will look if there is an existing matching deb
for the requested version. If one is found the download is skipped.
