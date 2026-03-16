## Clarify CLI help text for version arguments
<!--
type: bugfix
scope: all
affected: all
-->

The `--help` output for `cmk-dev-install` and `cmk-dev-site` was confusing in two ways:

- The positional argument was displayed as `version`, clashing with the `--version` flag.
  It now shows as `build-version` (`cmk-dev-install`) and `omd-version` (`cmk-dev-site`) to make the distinction clear.
- The date format for daily builds was only shown as a concrete example (e.g. `2.4.0-2025-01-01`),
  leaving the field order ambiguous. The help text now shows the format pattern (`YYYY-MM-DD` / `YYYY.MM.DD`) alongside the example.
