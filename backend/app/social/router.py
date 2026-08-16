import secrets
from datetime import datetime, timezone
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse

from app.config import settings
from app.crypto import encrypt_token
from app.db import social_connections
from app.dependencies import CurrentUser, require_full_plan, require_lojista
from app.models import SocialConnectionOut, SocialPageOut

router = APIRouter(prefix="/api/social", tags=["social"], dependencies=[Depends(require_full_plan)])

STATE_COOKIE = "meta_oauth_state"
GRAPH_BASE = f"https://graph.facebook.com/{settings.meta_graph_version}"

TIKTOK_STATE_COOKIE = "tiktok_oauth_state"
TIKTOK_AUTHORIZE_URL = "https://www.tiktok.com/v2/auth/authorize/"
TIKTOK_TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
TIKTOK_USER_INFO_URL = "https://open.tiktokapis.com/v2/user/info/"


@router.get("/meta/connect")
async def meta_connect(response: Response, user: CurrentUser = Depends(require_lojista)):
    if not settings.meta_app_id or not settings.meta_app_secret:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Conexão com o Meta não configurada")

    state = secrets.token_urlsafe(24)
    params = {
        "client_id": settings.meta_app_id,
        "redirect_uri": settings.meta_redirect_uri,
        "state": state,
        "response_type": "code",
        "scope": "pages_show_list,pages_manage_posts,instagram_business_basic,instagram_business_content_publish",
    }
    redirect = RedirectResponse(f"https://www.facebook.com/{settings.meta_graph_version}/dialog/oauth?{urlencode(params)}")
    redirect.set_cookie(
        STATE_COOKIE, state, httponly=True, secure=settings.cookie_secure, samesite="lax", max_age=300
    )
    return redirect


@router.get("/meta/callback")
async def meta_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    user: CurrentUser = Depends(require_lojista),
):
    expected_state = request.cookies.get(STATE_COOKIE)
    redirect = RedirectResponse(f"{settings.frontend_url}/trenddrop-pro.html?social=error")

    if error or not code or not state or not expected_state or state != expected_state:
        redirect.delete_cookie(STATE_COOKIE, path="/")
        return redirect

    try:
        async with httpx.AsyncClient() as client:
            short_resp = await client.get(
                f"{GRAPH_BASE}/oauth/access_token",
                params={
                    "client_id": settings.meta_app_id,
                    "redirect_uri": settings.meta_redirect_uri,
                    "client_secret": settings.meta_app_secret,
                    "code": code,
                },
            )
            short_resp.raise_for_status()
            short_token = short_resp.json()["access_token"]

            long_resp = await client.get(
                f"{GRAPH_BASE}/oauth/access_token",
                params={
                    "grant_type": "fb_exchange_token",
                    "client_id": settings.meta_app_id,
                    "client_secret": settings.meta_app_secret,
                    "fb_exchange_token": short_token,
                },
            )
            long_resp.raise_for_status()
            long_token = long_resp.json()["access_token"]

            accounts_resp = await client.get(
                f"{GRAPH_BASE}/me/accounts",
                params={"access_token": long_token},
            )
            accounts_resp.raise_for_status()
            raw_pages = accounts_resp.json().get("data", [])

            pages = []
            for raw_page in raw_pages:
                page_token = raw_page["access_token"]
                ig_resp = await client.get(
                    f"{GRAPH_BASE}/{raw_page['id']}",
                    params={"fields": "instagram_business_account", "access_token": page_token},
                )
                ig_data = ig_resp.json() if ig_resp.status_code == 200 else {}
                pages.append(
                    {
                        "page_id": raw_page["id"],
                        "name": raw_page["name"],
                        "access_token": encrypt_token(page_token),
                        "instagram_business_account_id": (ig_data.get("instagram_business_account") or {}).get("id"),
                    }
                )

        await social_connections.update_one(
            {"tenant_id": user.tenant_id, "platform": "meta"},
            {
                "$set": {
                    "connected": True,
                    "long_lived_token": encrypt_token(long_token),
                    "pages": pages,
                    "connected_at": datetime.now(timezone.utc),
                }
            },
            upsert=True,
        )
        redirect = RedirectResponse(f"{settings.frontend_url}/trenddrop-pro.html?social=connected")
    except Exception:
        redirect = RedirectResponse(f"{settings.frontend_url}/trenddrop-pro.html?social=error")

    redirect.delete_cookie(STATE_COOKIE, path="/")
    return redirect


@router.get("/connections", response_model=list[SocialConnectionOut])
async def list_social_connections(user: CurrentUser = Depends(require_lojista)):
    meta_doc = await social_connections.find_one({"tenant_id": user.tenant_id, "platform": "meta"})
    meta_out = SocialConnectionOut(
        platform="meta",
        configured=bool(settings.meta_app_id and settings.meta_app_secret),
        connected=bool(meta_doc and meta_doc.get("connected")),
        pages=[
            SocialPageOut(
                page_id=p["page_id"], name=p["name"], has_instagram=bool(p.get("instagram_business_account_id"))
            )
            for p in (meta_doc.get("pages", []) if meta_doc else [])
        ],
        connected_at=meta_doc.get("connected_at") if meta_doc else None,
    )
    tiktok_doc = await social_connections.find_one({"tenant_id": user.tenant_id, "platform": "tiktok"})
    tiktok_out = SocialConnectionOut(
        platform="tiktok",
        configured=bool(settings.tiktok_client_key and settings.tiktok_client_secret),
        connected=bool(tiktok_doc and tiktok_doc.get("connected")),
        pages=[],
        connected_at=tiktok_doc.get("connected_at") if tiktok_doc else None,
    )
    return [meta_out, tiktok_out]


@router.post("/meta/disconnect")
async def meta_disconnect(user: CurrentUser = Depends(require_lojista)):
    await social_connections.delete_one({"tenant_id": user.tenant_id, "platform": "meta"})
    return {"ok": True}


@router.get("/tiktok/connect")
async def tiktok_connect(response: Response, user: CurrentUser = Depends(require_lojista)):
    if not settings.tiktok_client_key or not settings.tiktok_client_secret:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Conexão com o TikTok não configurada")

    state = secrets.token_urlsafe(24)
    params = {
        "client_key": settings.tiktok_client_key,
        "redirect_uri": settings.tiktok_redirect_uri,
        "state": state,
        "response_type": "code",
        "scope": "user.info.basic",
    }
    redirect = RedirectResponse(f"{TIKTOK_AUTHORIZE_URL}?{urlencode(params)}")
    redirect.set_cookie(
        TIKTOK_STATE_COOKIE, state, httponly=True, secure=settings.cookie_secure, samesite="lax", max_age=300
    )
    return redirect


@router.get("/tiktok/callback")
async def tiktok_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    user: CurrentUser = Depends(require_lojista),
):
    expected_state = request.cookies.get(TIKTOK_STATE_COOKIE)
    redirect = RedirectResponse(f"{settings.frontend_url}/trenddrop-pro.html?social=error")

    if error or not code or not state or not expected_state or state != expected_state:
        redirect.delete_cookie(TIKTOK_STATE_COOKIE, path="/")
        return redirect

    try:
        async with httpx.AsyncClient() as client:
            token_resp = await client.post(
                TIKTOK_TOKEN_URL,
                data={
                    "client_key": settings.tiktok_client_key,
                    "client_secret": settings.tiktok_client_secret,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": settings.tiktok_redirect_uri,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            token_resp.raise_for_status()
            token_data = token_resp.json()
            access_token = token_data["access_token"]
            refresh_token = token_data.get("refresh_token")
            open_id = token_data.get("open_id")

            info_resp = await client.get(
                TIKTOK_USER_INFO_URL,
                params={"fields": "open_id,display_name,avatar_url"},
                headers={"Authorization": f"Bearer {access_token}"},
            )
            info_resp.raise_for_status()
            info_data = info_resp.json().get("data", {}).get("user", {})

        await social_connections.update_one(
            {"tenant_id": user.tenant_id, "platform": "tiktok"},
            {
                "$set": {
                    "connected": True,
                    "access_token": encrypt_token(access_token),
                    "refresh_token": encrypt_token(refresh_token) if refresh_token else None,
                    "open_id": open_id,
                    "display_name": info_data.get("display_name"),
                    "connected_at": datetime.now(timezone.utc),
                }
            },
            upsert=True,
        )
        redirect = RedirectResponse(f"{settings.frontend_url}/trenddrop-pro.html?social=connected")
    except Exception:
        redirect = RedirectResponse(f"{settings.frontend_url}/trenddrop-pro.html?social=error")

    redirect.delete_cookie(TIKTOK_STATE_COOKIE, path="/")
    return redirect


@router.post("/tiktok/disconnect")
async def tiktok_disconnect(user: CurrentUser = Depends(require_lojista)):
    await social_connections.delete_one({"tenant_id": user.tenant_id, "platform": "tiktok"})
    return {"ok": True}
