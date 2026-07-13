## Fix host creation on community edition
<!--
type: bugfix
scope: all
affected: all
-->

`cmk-dev-site` failed on the community edition when creating the site host:
the REST API rejected the `bake_agent` query parameter with "The bake_agent
field is not supported by this license", even though it was set to `False`.
The parameter is no longer sent at all — `False` is the API default, so
behavior is unchanged on editions that support the agent bakery, and host
creation now works on editions without it (e.g. community).
