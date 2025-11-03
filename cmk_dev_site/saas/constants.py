from pathlib import Path
from typing import Final

OIDC_PORT: Final = 8089
HOST: Final = "127.0.0.1"
URL: Final = f"http://{HOST}:{OIDC_PORT}"

CSE_CONFIG_DIR: Final = Path("/etc/cse")
OIDC_CONFIG_PATH: Final = CSE_CONFIG_DIR / "cognito-cmk.json"
ADMIN_PANEL_CONFIG_PATH: Final = CSE_CONFIG_DIR / "admin_panel_url.json"
TENANT_ID: Final = "092fd467-0d2f-4e0a-90b8-4ee6494f7453"  # a valid fixed uuid
