## Restructure python project
<!--
type: bugfix
scope: internal
affected: all
-->

Moved toplevel python modules into cmk_dev_site module.

This fixes

```
ModuleNotFoundError: No module named 'cmk'
```
