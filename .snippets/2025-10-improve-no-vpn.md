## reduce time for partialversion without vpn
<!--
type: bugfix
scope: all
affected: all
-->

Using the partial version without a VPN results in long wait times when searching for TSBUILDS, as the URL is inaccessible.
This change omits the TSBUILDS URL from the search, improving performance for users without a VPN.
