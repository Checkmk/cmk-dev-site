## Store the remote site CA like the GUI does
<!--
type: bugfix
scope: all
affected: all
-->

When connecting a remote site (`cmk-dev-install -d 1`), `cmk-dev-site` trusted
the remote site's CA but did not write
`~/var/ssl/remote_sites_cas/<remote>.pem` on the central site, which the GUI
writes when you trust a CA there. Without it, baking agents that register to the
remote site failed, and the data backend reported the remote site's CA as not
trusted. The file is now written as well.
