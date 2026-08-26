## Fix site connection creation on Checkmk 3.0.0 and newer
<!--
type: bugfix
scope: all
affected: all
-->

Setting up a distributed setup failed with

```
cmk_dev_site.cmk.rest_api.CheckmkAPIException: Failed to create site connection
```

because Checkmk 3.0.0 requires `authentication_connections` in the
`configuration_connection` part of the site connection payload. It is now sent
as `{"type": "disabled"}` for 3.0.0 and newer, matching the `user_sync` setting
next to it. Older versions do not know the field and reject payloads containing
it, so it is omitted there.
