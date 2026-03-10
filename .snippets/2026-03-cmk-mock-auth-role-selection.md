## Mock auth login page with role selection
<!--
type: feature
scope: all
affected: cloud
-->

Added an interactive login form to the mock OIDC service for local testing with different usernames and roles.

The `/authorize` endpoint now displays a plain HTML form with a username field (pre-filled with `test@test.com`) and radio buttons for `user` or `admin` role selection. The selected identity is carried through the OAuth flow and included in the issued JWT tokens.
