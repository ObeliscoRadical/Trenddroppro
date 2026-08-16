from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status

from app.content_ai import ContentGenerationError, generate_bundle
from app.db import catalog_products, content_bundles
from app.dependencies import CurrentUser, require_full_plan, require_lojista
from app.models import (
    BulkApproveIn,
    ContentBundleOut,
    GenerateContentIn,
    UpdateBundleIn,
)

router = APIRouter(prefix="/api/content", tags=["content"], dependencies=[Depends(require_full_plan)])


def _now_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)


async def _next_bundle_id(tenant_id: str) -> int:
    cursor = content_bundles.find({"tenant_id": tenant_id}, {"id": 1}).sort("id", -1).limit(1)
    docs = await cursor.to_list(length=1)
    return (docs[0]["id"] if docs else 0) + 1


async def _get_bundle(tenant_id: str, bundle_id: int) -> dict:
    doc = await content_bundles.find_one({"tenant_id": tenant_id, "id": bundle_id})
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Bundle não encontrado")
    return doc


def _to_out(doc: dict) -> ContentBundleOut:
    return ContentBundleOut(**{k: v for k, v in doc.items() if k not in ("_id", "tenant_id")})


@router.post("/generate", response_model=ContentBundleOut)
async def generate_content(data: GenerateContentIn, user: CurrentUser = Depends(require_lojista)):
    product = await catalog_products.find_one(
        {"tenant_id": user.tenant_id, "id": data.product_id, "status": "ativo"}
    )
    if not product:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Produto não encontrado")

    try:
        result = await generate_bundle(product)
    except ContentGenerationError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc))

    bundle = {
        "tenant_id": user.tenant_id,
        "id": await _next_bundle_id(user.tenant_id),
        "productId": product["id"],
        "productName": product["name"],
        "productEmoji": product["emoji"],
        "hooks": result["hooks"],
        "content": result["content"],
        "notes": "",
        "status": "pendente",
        "createdAt": _now_ms(),
    }
    await content_bundles.insert_one(bundle)
    return _to_out(bundle)


@router.get("/bundles", response_model=list[ContentBundleOut])
async def list_bundles(user: CurrentUser = Depends(require_lojista)):
    docs = await content_bundles.find({"tenant_id": user.tenant_id}).sort("id", -1).to_list(length=None)
    return [_to_out(d) for d in docs]


@router.patch("/bundles/{bundle_id}", response_model=ContentBundleOut)
async def update_bundle(bundle_id: int, data: UpdateBundleIn, user: CurrentUser = Depends(require_lojista)):
    await _get_bundle(user.tenant_id, bundle_id)
    updates = data.model_dump(exclude_unset=True, exclude_none=True)
    if updates:
        await content_bundles.update_one({"tenant_id": user.tenant_id, "id": bundle_id}, {"$set": updates})
    doc = await _get_bundle(user.tenant_id, bundle_id)
    return _to_out(doc)


@router.post("/bundles/{bundle_id}/approve", response_model=ContentBundleOut)
async def approve_bundle(bundle_id: int, user: CurrentUser = Depends(require_lojista)):
    await _get_bundle(user.tenant_id, bundle_id)
    await content_bundles.update_one(
        {"tenant_id": user.tenant_id, "id": bundle_id},
        {"$set": {"status": "aprovado", "approvedAt": _now_ms()}},
    )
    doc = await _get_bundle(user.tenant_id, bundle_id)
    return _to_out(doc)


@router.post("/bundles/approve-bulk")
async def approve_bundles_bulk(data: BulkApproveIn, user: CurrentUser = Depends(require_lojista)):
    result = await content_bundles.update_many(
        {"tenant_id": user.tenant_id, "id": {"$in": data.ids}},
        {"$set": {"status": "aprovado", "approvedAt": _now_ms()}},
    )
    return {"ok": True, "count": result.modified_count}
