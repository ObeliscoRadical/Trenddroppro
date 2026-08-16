from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status

from app.db import niches as niches_col
from app.db import products as products_col
from app.db import scan_usage
from app.dependencies import CurrentUser, get_current_user, require_lojista
from app.discovery import discover_product
from app.models import NicheOut, ProductOut, ScanResultOut

router = APIRouter(prefix="/api", tags=["catalog"], dependencies=[Depends(get_current_user)])

BASIC_DAILY_SCAN_LIMIT = 1


@router.get("/products", response_model=list[ProductOut])
async def list_products():
    return await products_col.find({}, {"_id": 0}).to_list(length=None)


@router.get("/niches", response_model=list[NicheOut])
async def list_niches():
    return await niches_col.find({}, {"_id": 0}).to_list(length=None)


async def _check_scan_allowed(tenant_id: str) -> None:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    doc = await scan_usage.find_one({"tenant_id": tenant_id, "date": today})
    count = doc["count"] if doc else 0
    if count >= BASIC_DAILY_SCAN_LIMIT:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Limite diário de scans do plano Básico atingido. Assine o Full para scans ilimitados.",
        )
    await scan_usage.update_one(
        {"tenant_id": tenant_id, "date": today},
        {"$inc": {"count": 1}},
        upsert=True,
    )


@router.post("/products/scan", response_model=ScanResultOut)
async def scan_for_trending_product(user: CurrentUser = Depends(require_lojista)):
    if user.plan == "basico":
        await _check_scan_allowed(user.tenant_id)
    product = await discover_product()
    return ScanResultOut(product=product)
