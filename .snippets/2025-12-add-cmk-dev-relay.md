## Add cmk-dev-relay command to setup a relay
<!--
type: feature
scope: all
affected: all
-->

Added `cmk-dev-relay` command to deploy and manage Checkmk relay pods for testing using podman.
The tool creates two types of relay environments: an isolated SNMP relay with a single test host, and a standard host relay for agent-based monitoring.
Supports building relay images locally or pulling from DockerHub to match the installed Checkmk version.
Includes automatic site detection from environment variables, `.site` files, or running OMD sites.
Provides subcommands for lifecycle management: `up`, `down`, `restart`, and `kill` to control relay pods and configurations.
