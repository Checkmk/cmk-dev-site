## Enable the MCP server and its usage data forwarding by default
<!--
type: feature
scope: all
affected: all
-->

`cmk-dev-site` now sets `MCP_SERVER=on` and `MCP_TRACE_FORWARD=on` when it
creates a site, so Checkmk's MCP server is reachable at
`http://localhost/<site>/check_mk/mcp` without any further setup:

```
$ cmk-dev-site
...
[v300]: Forwarding MCP usage data to Checkmk's telemetry collector (mcp-analytics.checkmk.com). Disable with --omd-configs MCP_TRACE_FORWARD=off
```

Both options are only set where the installed version and edition ship the
corresponding omd hooks (Checkmk 3.0.0 and newer, every edition except
community). Older versions and community sites are left untouched.

`MCP_TRACE_FORWARD` forwards the MCP server's OpenTelemetry traces (which tools
were called, response times and sizes, error codes, which AI client was used,
and a random session ID, but never request or result content) to Checkmk's
central telemetry collector.

Opt out of either with `--omd-configs`:

```
cmk-dev-site --omd-configs MCP_SERVER=off
cmk-dev-site --omd-configs MCP_TRACE_FORWARD=off
```
