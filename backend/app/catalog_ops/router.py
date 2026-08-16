from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status

from app.db import catalog_products, removal_queue
from app.dependencies import CurrentUser, require_full_plan, require_lojista
from app.models import (
    CatalogProductCreateIn,
    CatalogProductOut,
    CatalogProductUpdateIn,
    FlagForRemovalIn,
    RemovalQueueItemOut,
)

router = APIRouter(prefix="/api/catalog", tags=["catalog_ops"], dependencies=[Depends(require_full_plan)])

DEFAULT_FLAG_REASON = "Marcado manualmente para revisão."
DEFAULT_FLAG_ACTION = "Revisar performance e decidir manutenção ou remoção."


async def _next_product_id(tenant_id: str) -> int:
    cursor = catalog_products.find({"tenant_id": tenant_id}, {"id": 1}).sort("id", -1).limit(1)
    docs = await cursor.to_list(length=1)
    return (docs[0]["id"] if docs else 0) + 1


async def _get_product(tenant_id: str, product_id: int) -> dict:
    doc = await catalog_products.find_one({"tenant_id": tenant_id, "id": product_id})
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Produto não encontrado")
    return doc


@router.get("/products", response_model=list[CatalogProductOut])
async def list_catalog_products(user: CurrentUser = Depends(require_lojista)):
    return await catalog_products.find({"tenant_id": user.tenant_id}, {"_id": 0, "tenant_id": 0, "created_at": 0}).to_list(length=None)


@router.post("/products", response_model=CatalogProductOut, status_code=status.HTTP_201_CREATED)
async def create_catalog_product(data: CatalogProductCreateIn, user: CurrentUser = Depends(require_lojista)):
    product = {
        "tenant_id": user.tenant_id,
        "id": await _next_product_id(user.tenant_id),
        "status": "ativo",
        "created_at": datetime.now(timezone.utc),
        **data.model_dump(),
    }
    await catalog_products.insert_one(product)
    return CatalogProductOut(**{k: v for k, v in product.items() if k not in ("tenant_id", "created_at")})


@router.patch("/products/{product_id}", response_model=CatalogProductOut)
async def update_catalog_product(
    product_id: int, data: CatalogProductUpdateIn, user: CurrentUser = Depends(require_lojista)
):
    await _get_product(user.tenant_id, product_id)
    updates = {k: v for k, v in data.model_dump(exclude_unset=True).items() if v is not None}
    if updates:
        await catalog_products.update_one({"tenant_id": user.tenant_id, "id": product_id}, {"$set": updates})
    doc = await _get_product(user.tenant_id, product_id)
    return CatalogProductOut(**{k: v for k, v in doc.items() if k not in ("_id", "tenant_id", "created_at")})


@router.post("/products/{product_id}/flag", response_model=RemovalQueueItemOut)
async def flag_for_removal(
    product_id: int, data: FlagForRemovalIn, user: CurrentUser = Depends(require_lojista)
):
    product = await _get_product(user.tenant_id, product_id)
    if await removal_queue.find_one({"tenant_id": user.tenant_id, "catalog_product_id": product_id}):
        raise HTTPException(status.HTTP_409_CONFLICT, "Esse produto já está na fila")

    item = {
        "tenant_id": user.tenant_id,
        "catalog_product_id": product_id,
        "name": product["name"],
        "platform": product["platform"],
        "days": 0,
        "reason": data.reason or DEFAULT_FLAG_REASON,
        "metrics": {"cliques": str(product["clicks"]), "conversao": "—"},
        "action": DEFAULT_FLAG_ACTION,
        "created_at": datetime.now(timezone.utc),
    }
    await removal_queue.insert_one(item)
    return RemovalQueueItemOut(**{k: v for k, v in item.items() if k not in ("tenant_id", "created_at")})


@router.post("/products/{product_id}/keep")
async def keep_product(product_id: int, user: CurrentUser = Depends(require_lojista)):
    await removal_queue.delete_one({"tenant_id": user.tenant_id, "catalog_product_id": product_id})
    return {"ok": True}


@router.post("/products/{product_id}/confirm-removal")
async def confirm_removal(product_id: int, user: CurrentUser = Depends(require_lojista)):
    await _get_product(user.tenant_id, product_id)
    await removal_queue.delete_one({"tenant_id": user.tenant_id, "catalog_product_id": product_id})
    await catalog_products.update_one(
        {"tenant_id": user.tenant_id, "id": product_id}, {"$set": {"status": "removido"}}
    )
    return {"ok": True}


@router.get("/removal-queue", response_model=list[RemovalQueueItemOut])
async def list_removal_queue(user: CurrentUser = Depends(require_lojista)):
    return await removal_queue.find({"tenant_id": user.tenant_id}, {"_id": 0, "tenant_id": 0, "created_at": 0}).to_list(length=None)
