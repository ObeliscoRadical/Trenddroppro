from collections import defaultdict
from datetime import datetime, timedelta, timezone

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status

from app.db import tenants, users
from app.dependencies import require_admin
from app.models import AdminMetricsOut, TenantAdminOut, TenantStatusIn

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)])


async def _owners_by_tenant() -> dict[str, list[dict]]:
    owners = defaultdict(list)
    async for u in users.find({"role": "lojista"}, {"tenant_id": 1, "nome": 1, "email": 1}):
        if u.get("tenant_id"):
            owners[u["tenant_id"]].append(u)
    return owners


@router.get("/tenants", response_model=list[TenantAdminOut])
async def list_tenants():
    owners = await _owners_by_tenant()
    result = []
    async for t in tenants.find({}):
        tenant_id = str(t["_id"])
        tenant_owners = owners.get(tenant_id, [])
        first_owner = tenant_owners[0] if tenant_owners else None
        result.append(
            TenantAdminOut(
                id=tenant_id,
                nome_loja=t["nome_loja"],
                status=t.get("status", "active"),
                created_at=t["created_at"],
                owner_nome=first_owner["nome"] if first_owner else None,
                owner_email=first_owner["email"] if first_owner else None,
                user_count=len(tenant_owners),
            )
        )
    result.sort(key=lambda t: t.created_at, reverse=True)
    return result


@router.patch("/tenants/{tenant_id}/status", response_model=TenantAdminOut)
async def update_tenant_status(tenant_id: str, data: TenantStatusIn):
    try:
        oid = ObjectId(tenant_id)
    except Exception:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Loja não encontrada")

    result = await tenants.update_one({"_id": oid}, {"$set": {"status": data.status}})
    if result.matched_count == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Loja não encontrada")

    t = await tenants.find_one({"_id": oid})
    owners = await _owners_by_tenant()
    tenant_owners = owners.get(tenant_id, [])
    first_owner = tenant_owners[0] if tenant_owners else None
    return TenantAdminOut(
        id=tenant_id,
        nome_loja=t["nome_loja"],
        status=t.get("status", "active"),
        created_at=t["created_at"],
        owner_nome=first_owner["nome"] if first_owner else None,
        owner_email=first_owner["email"] if first_owner else None,
        user_count=len(tenant_owners),
    )


@router.get("/metrics", response_model=AdminMetricsOut)
async def metrics():
    total = await tenants.count_documents({})
    ativas = await tenants.count_documents({"status": "active"})
    suspensas = await tenants.count_documents({"status": "suspended"})
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    novas = await tenants.count_documents({"created_at": {"$gte": cutoff.replace(tzinfo=None)}})
    return AdminMetricsOut(
        total_lojas=total,
        lojas_ativas=ativas,
        lojas_suspensas=suspensas,
        novas_ultimos_30_dias=novas,
    )
