## Add cmk-dev as universal wrapper for all tools contained in this project
<!--
type: feature
scope: all
affected: all
-->

Added a new `cmk-dev` command that provides a unified interface to all cmk-dev-* tools.
Instead of remembering multiple command names, users can now run `cmk-dev <tool> <args>` where tool is one of: install, site, install-site, or site-mock-auth.
 The wrapper includes comprehensive tests to ensure all entrypoints defined in pyproject.toml are properly wrapped.
