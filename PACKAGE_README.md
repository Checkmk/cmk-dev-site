# cmk-dev-site

_Easy Install Checkmk_

Scripts to install bleeding edge Checkmk in development context.

```
# Download and install latest available daily build of 2.5.0
cmk-dev-install 2.5 && cmk-dev-site

# Download daily build of today and
# setup distributed monitoring with one two sites:
cmk-dev-install 2.5.0-daily && cmk-dev-site -d 1
```

If you are a regular Checkmk customer you probably don't want to use this,
as this tools remove sites without warning.
