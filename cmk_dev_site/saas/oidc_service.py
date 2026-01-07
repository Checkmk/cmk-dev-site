"""This module sets up a fake OIDC provider and saas fine-grained authorization endpoints
using FastAPI. It can be used for end-to-end tests without requiring an external identity provider.

The module provides:
    - All endpoints required by the OIDC standard.
    - Tenant mapping for authorization.

Note: the signed-in user is hardcoded and cannot be changed.
"""

import argparse
import base64
import logging
from binascii import unhexlify
from collections.abc import Mapping, Sequence
from typing import Annotated, Literal
from urllib.parse import urlencode

import fastapi as fapi
import jwt
import uvicorn
from cryptography.hazmat.primitives.asymmetric import rsa
from pydantic import BaseModel

from cmk_dev_site.cmk_dev_site import ensure_sudo
from cmk_dev_site.saas.config import AdminPanelUrlConfig, OIDCConfig
from cmk_dev_site.saas.constants import (
    ADMIN_PANEL_CONFIG_PATH,
    HOST,
    OIDC_CONFIG_PATH,
    OIDC_PORT,
    TENANT_ID,
    URL,
)
from cmk_dev_site.utils import is_port_in_use, write_root_owned_file
from cmk_dev_site.utils.cli import clean_cli_exit
from cmk_dev_site.utils.log import get_logger

application = fapi.FastAPI()
logger = get_logger(__name__)


class TenantInfo(BaseModel):
    user_role: Literal["user", "admin"]


class UserRoleAnswer(BaseModel):
    tenants: Mapping[str, TenantInfo]


class WellKnownResponseModel(BaseModel):
    authorization_endpoint: str
    token_endpoint: str
    jwks_uri: str
    issuer: str = "checkmk"
    scopes_supported: Sequence[str] = ["openid", "email"]
    response_types_supported: Sequence[str] = ["code", "token"]
    id_token_signing_alg_values_supported: Sequence[str] = ["RS256"]
    subject_types_supported: Sequence[str] = ["public"]
    token_endpoint_auth_methods_supported: Sequence[str] = ["client_secret_post"]
    grant_types_supported: Sequence[str] = ["authorization_code"]


class JWKS:
    def __init__(self) -> None:
        # this is a mock testsetup to key-size is not to important
        self.private = rsa.generate_private_key(public_exponent=65537, key_size=1024)
        self.public = self.private.public_key()
        self.kid = "usethis"

    @property
    def n(self) -> str:
        n = self.public.public_numbers().n
        hexi = hex(n).lstrip("0x")
        encoded = base64.urlsafe_b64encode(unhexlify(hexi))
        return encoded.decode("utf-8").rstrip("=")


KEY = JWKS()


class KeyModel(BaseModel):
    n: str
    alg: str = "RS256"
    e: str = "AQAB"
    kid: str
    use: str = "sig"
    kty: str = "RSA"


class JWKSModel(BaseModel):
    keys: Sequence[KeyModel]


class TokenResponse(BaseModel):
    id_token: str
    access_token: str


class TokenPayload(BaseModel):
    email: str
    aud: str
    sub: str = "1234567"


@application.get("/.well-known/openid-configuration", status_code=200)
def well_known() -> WellKnownResponseModel:
    return WellKnownResponseModel(
        authorization_endpoint=f"{URL}/authorize",
        jwks_uri=f"{URL}/.well-known/jwks.json",
        token_endpoint=f"{URL}/token",
    )


@application.get("/.well-known/jwks.json", response_model=JWKSModel)
def jwks() -> JWKSModel:
    key = KeyModel(n=KEY.n, kid=KEY.kid)
    return JWKSModel(keys=[key])


@application.get("/healthz", status_code=200, responses={200: {}})
def liveness() -> str:
    return "I'm alive"


@application.post("/token", response_model=TokenResponse)
def token(client_id: Annotated[str, fapi.Form()]) -> TokenResponse:
    payload = TokenPayload(email="test@test.com", aud=client_id)
    id_token = jwt.encode(
        payload.model_dump(), KEY.private, algorithm="RS256", headers={"kid": KEY.kid}
    )
    # access token can be a random secret string. id-token is good enough for this fake
    return TokenResponse(id_token=id_token, access_token=id_token)


@application.get("/authorize")
def authorize(state: str, redirect_uri: str) -> fapi.responses.RedirectResponse:
    params = {"state": state, "code": "fake"}
    url = f"{redirect_uri}?{urlencode(params)}"
    return fapi.responses.RedirectResponse(url)


# this endpoint is used by checkmk to authorize the user on a site
# given he belongs to the right tenant
@application.get("/api/users/me/tenants")
def tenant_role_mapping() -> UserRoleAnswer:
    return UserRoleAnswer(tenants={TENANT_ID: TenantInfo(user_role="admin")})


@application.get("/logout")
def logout(client_id: str, redirect_uri: str) -> fapi.responses.RedirectResponse:
    return fapi.responses.RedirectResponse(redirect_uri)


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="increase output verbosity",
    )
    return p.parse_args()


def run() -> None:
    with clean_cli_exit():
        args = _parse_args()
        log_level = logging.DEBUG if args.verbose >= 1 else logging.INFO
        logger.setLevel(log_level)

        if is_port_in_use(OIDC_PORT):
            logger.info("OIDC port is used. Assume fake provider is running")
            return

        ensure_sudo()

        logger.debug("writing config")
        config = OIDCConfig()
        write_root_owned_file(OIDC_CONFIG_PATH, config.model_dump_json(indent=4))

        admin_panel = AdminPanelUrlConfig()
        write_root_owned_file(ADMIN_PANEL_CONFIG_PATH, admin_panel.model_dump_json(indent=4))

        logger.debug("starting uvicorn")
        uvicorn.run(application, port=OIDC_PORT, host=HOST, log_level=log_level)
