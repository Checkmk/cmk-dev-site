## fix silent failure for remove package
<!--
type: bugfix
scope: all
affected: all
-->

Removal of packages in cmk-dev-install occasionally resulted in errors due to f12 in the site.
Now we check if the package exists and remove the package without silenting the raising error to ensure we get the correct error at the end.
Additionally, the package directory is removed before the package removal to resolve the aforementioned issue.
