## Turn on the AI assistant's experimental flag by default
<!--
type: feature
scope: all
affected: all
-->

`cmk-dev-site` now turns on Checkmk's `exp_ai_assistant` experimental flag
when it creates a central site on a Checkmk version that ships the AI
assistant (the non-free editions of 2.5.0p14 and later, and of 3.0.0 builds
from late September 2026 on). So the AI assistant settings show in Global
settings without any further setup.

The flag does not start the AI assistant service. To start it, make sure the
global setting "Enable the AI assistant" is on, save it, and activate changes.
On Checkmk versions where that setting is on by default (current 3.0.0 builds),
the activation at the end of a distributed run (`-d N`) already starts the
service on the central site, because connecting a remote site queues the change. No AI
provider is configured, so the assistant asks you to select one.

`cmk-dev-site` does not set the flag on other versions or on remote sites.

Leave the flag off with:

```
cmk-dev-site --no-ai-assistant
```
