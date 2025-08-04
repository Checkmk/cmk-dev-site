## Command won't log in verbose mode
<!--
type: bugfix
scope: all
affected: all
-->

The `run_command` function is now wrapped by the caller module to automatically log both stdout and stderr for each command in verbose mode, unless logging is explicitly disabled.

