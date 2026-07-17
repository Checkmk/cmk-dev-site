## Pin fastapi below 1.0 to avoid a broken TestPyPI squatter package
<!--
type: bugfix
scope: internal
affected: all
-->

Installing a release candidate from test.pypi.org could fail because the
unpinned `fastapi` dependency resolved to a junk `FASTAPI 1.0` squatter
package hosted there, whose broken sdist fails to build
(`FileNotFoundError: DESCRIPTION.txt`).

`fastapi` is now constrained to `>=0.115,<1`, so this specific squatter is
excluded from resolution. This only fixes the fastapi build failure: mixing
`-i https://test.pypi.org/simple/` with `--extra-index-url
https://pypi.org/simple` still lets any *other* dependency be shadowed by a
higher-versioned package on test.pypi.org (a dependency-confusion risk, since
anyone can publish any package name there). Fetch only our own package from
test.pypi.org and resolve every dependency from pypi.org alone instead:

```
pip download --no-cache-dir --no-deps -d /tmp/rc-wheel \
    -i https://test.pypi.org/simple/ cmk-dev-site==<VERSION_WITH_RC>
pip install --no-cache-dir --force-reinstall /tmp/rc-wheel/cmk_dev_site-*.whl
```
