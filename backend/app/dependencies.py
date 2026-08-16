import jwt
from bson import ObjectId
from bson.errors import InvalidId
from fastapi import Depends, HTTPException, Request, status

from app.db import tenants, users
from app.security import decode_access_token


class CurrentUser:
    def __init__(self, doc: dict, plan: str = "basico"):
        self.id = str(doc["_id"])
        self.email = doc["email"]
        self.nome = doc["nome"]
        self.role = doc["role"]
        self.tenant_id = doc.get("tenant_id")
        self.is_active = doc.get("is_active", True)
        self.plan = plan


async def get_current_user(request: Request) -> CurrentUser:
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Não autenticado")
    try:
        payload = decode_access_token(token)
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sessão inválida ou expirada")

    try:
        oid = ObjectId(payload["sub"])
    except (InvalidId, TypeError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sessão inválida")

    doc = await users.find_one({"_id": oid})
    if not doc or not doc.get("is_active", True):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Conta inativa ou inexistente")

    plan = "basico"
    if doc.get("tenant_id"):
        tenant_doc = await tenants.find_one({"_id": ObjectId(doc["tenant_id"])})
        if not tenant_doc or tenant_doc.get("status") != "active":
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Loja suspensa. Entre em contato com o suporte.")
        plan = tenant_doc.get("plan", "basico")

    return CurrentUser(doc, plan=plan)


async def require_lojista(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if user.role != "lojista":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Acesso restrito a lojistas")
    return user


async def require_admin(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Acesso restrito a administradores")
    return user


async def require_full_plan(user: CurrentUser = Depends(require_lojista)) -> CurrentUser:
    if user.plan != "full":
        raise HTTPException(status.HTTP_402_PAYMENT_REQUIRED, "Esse recurso é exclusivo do plano Full")
    return user
