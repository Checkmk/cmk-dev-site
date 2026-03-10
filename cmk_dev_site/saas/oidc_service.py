"""This module sets up a fake OIDC provider and saas fine-grained authorization endpoints
using FastAPI. It can be used for end-to-end tests without requiring an external identity provider.

The module provides:
    - All endpoints required by the OIDC standard.
    - Tenant mapping for authorization.

Note: the signed-in user is hardcoded and cannot be changed.
"""

import argparse
import base64
import html
import logging
import secrets
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
    user_role: Literal["user", "admin"]
    tenant_id: str = TENANT_ID


class AuthorizationCodeData(BaseModel):
    username: str
    user_role: Literal["user", "admin"]


DEFAULT_USERNAME = "test@test.com"
DEFAULT_ROLE: Literal["user", "admin"] = "admin"
AUTHORIZATION_CODES: dict[str, AuthorizationCodeData] = {}


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
def token(
    client_id: Annotated[str, fapi.Form()], code: Annotated[str, fapi.Form()]
) -> TokenResponse:
    try:
        login_data = AUTHORIZATION_CODES.pop(code)
    except KeyError as exc:
        raise fapi.HTTPException(status_code=400, detail="Invalid authorization code") from exc

    payload = TokenPayload(
        email=login_data.username,
        aud=client_id,
        sub=login_data.username,
        user_role=login_data.user_role,
    )
    id_token = jwt.encode(
        payload.model_dump(), KEY.private, algorithm="RS256", headers={"kid": KEY.kid}
    )
    return TokenResponse(id_token=id_token, access_token=id_token)


@application.get("/api/users/me/tenants")
def tenant_role_mapping(
    authorization: Annotated[str | None, fapi.Header()] = None,
) -> UserRoleAnswer:
    if authorization is None:
        raise fapi.HTTPException(status_code=401, detail="Missing Authorization header")

    scheme, _, token_str = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token_str:
        raise fapi.HTTPException(status_code=401, detail="Invalid Authorization header")

    try:
        decoded = jwt.decode(
            token_str, KEY.public, algorithms=["RS256"], options={"verify_aud": False}
        )
        payload = TokenPayload.model_validate(decoded)
    except jwt.InvalidTokenError as exc:
        raise fapi.HTTPException(status_code=401, detail="Invalid token") from exc

    return UserRoleAnswer(tenants={payload.tenant_id: TenantInfo(user_role=payload.user_role)})


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


@application.get("/authorize")
def authorize(state: str, redirect_uri: str) -> fapi.responses.HTMLResponse:
    escaped_state = html.escape(state, quote=True)
    escaped_redirect_uri = html.escape(redirect_uri, quote=True)
    escaped_username = html.escape(DEFAULT_USERNAME, quote=True)
    checked_user = " checked" if DEFAULT_ROLE == "user" else ""
    checked_admin = " checked" if DEFAULT_ROLE == "admin" else ""

    page = f"""<!doctype html>
<html>
<body>
<form method="post" action="/authorize">
<input type="hidden" name="state" value="{escaped_state}">
<input type="hidden" name="redirect_uri" value="{escaped_redirect_uri}">
<label>Username <input type="text" name="username" value="{escaped_username}"></label>
<label><input type="radio" name="role" value="user"{checked_user}> user</label>
<label><input type="radio" name="role" value="admin"{checked_admin}> admin</label>
<button type="submit">Login</button>
</form>
</body>
</html>"""
    return fapi.responses.HTMLResponse(page)


@application.post("/authorize")
def authorize_login(
    state: Annotated[str, fapi.Form()],
    redirect_uri: Annotated[str, fapi.Form()],
    username: Annotated[str, fapi.Form()],
    role: Annotated[Literal["user", "admin"], fapi.Form()],
) -> fapi.responses.RedirectResponse:
    code = secrets.token_urlsafe(16)
    AUTHORIZATION_CODES[code] = AuthorizationCodeData(username=username, user_role=role)
    params = {"state": state, "code": code}
    url = f"{redirect_uri}?{urlencode(params)}"
    return fapi.responses.RedirectResponse(url, status_code=303)
