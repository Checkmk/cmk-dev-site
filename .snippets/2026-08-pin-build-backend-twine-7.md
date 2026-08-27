## Fix package build failing on `twine check`
<!--
type: bugfix
scope: internal
affected: all
-->

Building the package failed with

```
InvalidDistribution: Invalid distribution metadata: '2.5' is not a valid metadata version
```

`hatchling` 1.32.0 writes `Metadata-Version: 2.5`, but `twine` 6.x refuses
anything above 2.4 from a hard-coded list in its own source, so no `packaging`
update can help. `twine` is now `>=7,<8`, which validates via `packaging`
instead.

The build backend was also unpinned and resolved fresh from PyPI on every CI
run, so the produced artifacts could change without a commit. `uv build` is now
called with `--build-constraints build-constraints.txt`, which pins
`hatchling==1.32.0`. The pin lives in the constraints file rather than in
`[build-system] requires`, because that field ships in the sdist and would
force the exact version on everyone building from source.
