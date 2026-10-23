## Install noble packages on Ubuntu 26.04 (resolute)
<!--
type: feature
scope: all
affected: all
-->

`cmk-dev-install` now works on Ubuntu 26.04 "resolute". It still prefers a
native resolute package; when none is available for the requested version, it
installs the Ubuntu 24.04 "noble" package instead and logs a warning. Git
versions are built for noble on resolute hosts.
