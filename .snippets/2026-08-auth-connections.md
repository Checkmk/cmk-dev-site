## Fix site connection creation on recent Checkmk versions
<!--
type: bugfix
scope: all
affected: all
-->

Setting up a distributed setup failed with

```
cmk_dev_site.cmk.rest_api.CheckmkAPIException: Failed to create site connection
```

because recent Checkmk versions require `authentication_connections` in the
`configuration_connection` part of the site connection payload. It is now sent
as `{"type": "disabled"}`, matching the `user_sync` setting next to it.
