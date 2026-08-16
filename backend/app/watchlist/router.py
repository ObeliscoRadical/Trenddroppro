from fastapi import APIRouter, Depends, HTTPException, status

from app.db import products as products_col
from app.db import watchlist as watchlist_col
from app.dependencies import CurrentUser, require_lojista
from app.models import WatchlistAddIn

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])


@router.get("", response_model=list[int])
async def get_watchlist(user: CurrentUser = Depends(require_lojista)):
    docs = await watchlist_col.find({"tenant_id": user.tenant_id}, {"product_id": 1}).to_list(length=None)
    return [d["product_id"] for d in docs]


@router.post("", status_code=status.HTTP_201_CREATED)
async def add_to_watchlist(data: WatchlistAddIn, user: CurrentUser = Depends(require_lojista)):
    if not await products_col.find_one({"id": data.product_id}):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Produto não encontrado")

    await watchlist_col.update_one(
        {"tenant_id": user.tenant_id, "product_id": data.product_id},
        {"$setOnInsert": {"tenant_id": user.tenant_id, "product_id": data.product_id}},
        upsert=True,
    )
    return {"ok": True}


@router.delete("/{product_id}")
async def remove_from_watchlist(product_id: int, user: CurrentUser = Depends(require_lojista)):
    await watchlist_col.delete_one({"tenant_id": user.tenant_id, "product_id": product_id})
    return {"ok": True}
