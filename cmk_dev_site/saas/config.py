from pathlib import Path

from pydantic import BaseModel

from cmk_dev_site.saas.constants import OIDC_CONFIG_PATH, TENANT_ID, URL


class OIDCConfig(BaseModel):
    base_url: str = "http://localhost"
    client_id: str = "notused"
    tenant_id: str = TENANT_ID
    well_known: str = f"{URL}/.well-known/openid-configuration"
    saas_api_url: str = URL
    logout_url: str = f"{URL}/logout"


def load_config() -> OIDCConfig:
    with open(OIDC_CONFIG_PATH, encoding="utf-8") as file:
        return OIDCConfig.model_validate_json(file.read())


def write_model(model: BaseModel, path: Path) -> None:
    with open(path, encoding="utf-8", mode="w") as file:
        file.write(model.model_dump_json(indent=4))


class AdminPanelUrlConfig(BaseModel):
    uap_url: str = "https://admin-panel.saas-prod.cloudsandbox.checkmk.cloud/"
    bug_tracker_url: str = "https://admin-panel.saas-prod.cloudsandbox.checkmk.cloud/bug-report"
    download_agent_user: str = "automation"
    tenant_id: str = TENANT_ID
