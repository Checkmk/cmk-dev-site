## Show how long a command took
<!--
type: feature
scope: all
affected: all
-->

`cmk-dev-install`, `cmk-dev-site` and `cmk-dev-install-site` now print how long
they took once they are done:

```
$ cmk-dev-install-site 2.5.0
...

Took 2m 05s
```

`cmk-dev-install-site` shows a single total for the installation and the site
setup together. The time is also shown if the command fails or is interrupted
with Ctrl-C. Runs shorter than a second, such as `--help`, stay quiet.
