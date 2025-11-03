## Add a mock auth service to run the cse
<!--
type: feature
scope: all
affected: all
-->

Added a fake OIDC provider to enable local development and testing of CSE sites without requiring external authentication services.
The mock authentication service implements all required OIDC endpoints and supports tenant-based authorization.

**Key additions:**
- New `mock-auth` command to start the fake OIDC provider on port 10080
- Automatic generation of CSE configuration files (`/etc/cse/cognito-cmk.json` and `/etc/cse/admin_panel_url.json`)
- Port availability check when creating CSE sites to ensure mock-auth is running
- Complete OIDC flow implementation including token generation, JWKS endpoints, and authorization
- Fixed tenant ID for consistent testing (`092fd467-0d2f-4e0a-90b8-4ee6494f7453`)

To use: Run `mock-auth` before creating CSE sites with `cmk-dev-site`.
