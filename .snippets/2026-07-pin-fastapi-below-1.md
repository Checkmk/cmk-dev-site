## Pin fastapi below 1.0 to make TestPyPI installs work
<!--
type: bugfix
scope: internal
affected: all
-->

Installing a release candidate from test.pypi.org failed because the
unpinned `fastapi` dependency resolved to a junk `FASTAPI 1.0` squatter
package hosted there, whose broken sdist fails to build
(`FileNotFoundError: DESCRIPTION.txt`).

`fastapi` is now constrained to `>=0.115,<1`, so pip skips the squatter and
resolves the real fastapi from pypi.org. This makes the documented rc test
command work again:

```
pip install --no-cache-dir \
    -i https://test.pypi.org/simple/ \
    --extra-index-url https://pypi.org/simple \
    cmk-dev-site==<VERSION_WITH_RC>
```
