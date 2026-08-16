from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.config import settings
from app.db import refresh_tokens, tenants, users
from app.dependencies import CurrentUser, get_current_user
from app.models import LoginIn, SignupIn, TenantDoc, UserDoc, UserOut, utcnow
from app.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])

ACCESS_COOKIE = "access_token"
REFRESH_COOKIE = "refresh_token"


def _cookie_kwargs(max_age: int) -> dict:
    return dict(
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=max_age,
        path="/",
    )


async def _issue_session(response: Response, *, user_id: str, role: str, tenant_id: str | None) -> None:
    access_token = create_access_token(user_id=user_id, role=role, tenant_id=tenant_id)
    raw_refresh, refresh_hash, expires_at = generate_refresh_token()

    await refresh_tokens.insert_one(
        {
            "user_id": ObjectId(user_id),
            "token_hash": refresh_hash,
            "expires_at": expires_at,
            "revoked_at": None,
            "created_at": datetime.now(timezone.utc),
        }
    )

    response.set_cookie(ACCESS_COOKIE, access_token, **_cookie_kwargs(settings.access_token_ttl_min * 60))
    response.set_cookie(
        REFRESH_COOKIE, raw_refresh, **_cookie_kwargs(settings.refresh_token_ttl_days * 24 * 3600)
    )


def _clear_session_cookies(response: Response) -> None:
    response.delete_cookie(ACCESS_COOKIE, path="/")
    response.delete_cookie(REFRESH_COOKIE, path="/")


async def _build_user_out(doc: dict) -> UserOut:
    loja = None
    plan = "basico"
    if doc.get("tenant_id"):
        tenant_doc = await tenants.find_one({"_id": ObjectId(doc["tenant_id"])})
        if tenant_doc:
            loja = tenant_doc["nome_loja"]
            plan = tenant_doc.get("plan", "basico")
    return UserOut(
        id=str(doc["_id"]),
        email=doc["email"],
        nome=doc["nome"],
        role=doc["role"],
        tenant_id=doc.get("tenant_id"),
        loja=loja,
        auth_method="google" if doc.get("google_id") else "email",
        plan=plan,
    )


@router.post("/signup", response_model=UserOut)
async def signup(data: SignupIn, response: Response):
    if not data.terms_accepted:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "É preciso aceitar os Termos de Uso e a Política de Privacidade")
    if await users.find_one({"email": data.email}):
        raise HTTPException(status.HTTP_409_CONFLICT, "Já existe uma conta com este e-mail")

    tenant = TenantDoc(nome_loja=data.loja)
    tenant_result = await tenants.insert_one(tenant.model_dump())
    tenant_id = str(tenant_result.inserted_id)

    user = UserDoc(
        tenant_id=tenant_id,
        email=data.email,
        nome=data.nome,
        role="lojista",
        password_hash=hash_password(data.senha),
        terms_accepted_at=utcnow(),
    )
    user_result = await users.insert_one(user.model_dump())
    user_id = str(user_result.inserted_id)

    await _issue_session(response, user_id=user_id, role="lojista", tenant_id=tenant_id)

    doc = await users.find_one({"_id": user_result.inserted_id})
    return await _build_user_out(doc)


@router.post("/login", response_model=UserOut)
async def login(data: LoginIn, response: Response):
    doc = await users.find_one({"email": data.email})
    if not doc or not doc.get("password_hash") or not verify_password(data.senha, doc["password_hash"]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "E-mail ou senha inválidos")
    if not doc.get("is_active", True):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Conta desativada")

    if doc.get("tenant_id"):
        tenant_doc = await tenants.find_one({"_id": ObjectId(doc["tenant_id"])})
        if not tenant_doc or tenant_doc.get("status") != "active":
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Loja suspensa. Entre em contato com o suporte.")

    await _issue_session(
        response, user_id=str(doc["_id"]), role=doc["role"], tenant_id=doc.get("tenant_id")
    )
    return await _build_user_out(doc)


@router.post("/refresh", response_model=UserOut)
async def refresh(request: Request, response: Response):
    raw = request.cookies.get(REFRESH_COOKIE)
    if not raw:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sem sessão para renovar")

    token_hash = hash_refresh_token(raw)
    record = await refresh_tokens.find_one({"token_hash": token_hash})
    now = datetime.now(timezone.utc)
    if (
        not record
        or record.get("revoked_at") is not None
        or record["expires_at"].replace(tzinfo=timezone.utc) < now
    ):
        _clear_session_cookies(response)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sessão expirada, faça login novamente")

    await refresh_tokens.update_one({"_id": record["_id"]}, {"$set": {"revoked_at": now}})

    doc = await users.find_one({"_id": record["user_id"]})
    if not doc or not doc.get("is_active", True):
        _clear_session_cookies(response)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Conta inativa ou inexistente")

    await _issue_session(
        response, user_id=str(doc["_id"]), role=doc["role"], tenant_id=doc.get("tenant_id")
    )
    return await _build_user_out(doc)


@router.post("/logout")
async def logout(request: Request, response: Response):
    raw = request.cookies.get(REFRESH_COOKIE)
    if raw:
        await refresh_tokens.update_one(
            {"token_hash": hash_refresh_token(raw)},
            {"$set": {"revoked_at": datetime.now(timezone.utc)}},
        )
    _clear_session_cookies(response)
    return {"ok": True}


@router.get("/me", response_model=UserOut)
async def me(current: CurrentUser = Depends(get_current_user)):
    doc = await users.find_one({"_id": ObjectId(current.id)})
    return await _build_user_out(doc)
