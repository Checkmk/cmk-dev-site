## Create also a site if trace tooling is not installed
<!--
type: bugfix
scope: external
affected: all
-->

Tracing is not supported on all editions (not the CSE). In case we cannot setup tracing during
site creation just print a warning and leave tracing unconfigured.
