import secrets
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse

from app.auth.router import _issue_session
from app.config import settings
from app.db import tenants, users
from app.models import TenantDoc, UserDoc, utcnow

router = APIRouter(prefix="/api/auth/google", tags=["auth"])

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"
STATE_COOKIE = "oauth_state"


@router.get("/login")
async def google_login(response: Response):
    if not settings.google_client_id:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Login com Google não configurado")

    state = secrets.token_urlsafe(24)
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "prompt": "select_account",
    }
    redirect = RedirectResponse(f"{AUTH_URL}?{urlencode(params)}")
    redirect.set_cookie(
        STATE_COOKIE, state, httponly=True, secure=settings.cookie_secure, samesite="lax", max_age=300
    )
    return redirect


@router.get("/callback")
async def google_callback(request: Request, code: str | None = None, state: str | None = None, error: str | None = None):
    expected_state = request.cookies.get(STATE_COOKIE)
    if error or not code or not state or not expected_state or state != expected_state:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Falha na autenticação com Google")

    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": settings.google_redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        if token_resp.status_code != 200:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Não foi possível validar o login com Google")
        access_token = token_resp.json()["access_token"]

        userinfo_resp = await client.get(USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"})
        if userinfo_resp.status_code != 200:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Não foi possível obter dados do Google")
        profile = userinfo_resp.json()

    google_id = profile["sub"]
    email = profile["email"]
    nome = profile.get("name") or email.split("@")[0]

    doc = await users.find_one({"google_id": google_id})
    if not doc:
        doc = await users.find_one({"email": email})
        if doc:
            await users.update_one({"_id": doc["_id"]}, {"$set": {"google_id": google_id}})
            doc["google_id"] = google_id

    if not doc:
        primeiro_nome = nome.split(" ")[0]
        tenant = TenantDoc(nome_loja=f"Loja de {primeiro_nome}")
        tenant_result = await tenants.insert_one(tenant.model_dump())
        tenant_id = str(tenant_result.inserted_id)

        user = UserDoc(
            tenant_id=tenant_id, email=email, nome=nome, role="lojista", google_id=google_id,
            terms_accepted_at=utcnow(),
        )
        user_result = await users.insert_one(user.model_dump())
        doc = await users.find_one({"_id": user_result.inserted_id})

    if not doc.get("is_active", True):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Conta desativada")

    redirect = RedirectResponse(settings.frontend_url)
    await _issue_session(
        redirect, user_id=str(doc["_id"]), role=doc["role"], tenant_id=doc.get("tenant_id")
    )
    redirect.delete_cookie(STATE_COOKIE, path="/")
    return redirect
