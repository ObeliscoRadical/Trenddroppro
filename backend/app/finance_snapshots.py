from datetime import datetime, timezone

from app.db import catalog_products, revenue_snapshots, tenants


def _today_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


async def compute_total_revenue(tenant_id: str) -> float:
    total = 0.0
    async for p in catalog_products.find({"tenant_id": tenant_id, "status": "ativo"}, {"revenue": 1}):
        total += p.get("revenue", 0) or 0
    return total


async def ensure_snapshot_today(tenant_id: str) -> None:
    total = await compute_total_revenue(tenant_id)
    await revenue_snapshots.update_one(
        {"tenant_id": tenant_id, "date": _today_str()},
        {"$set": {"totalRevenue": total}, "$setOnInsert": {"createdAt": datetime.now(timezone.utc)}},
        upsert=True,
    )


async def snapshot_all_tenants() -> None:
    async for t in tenants.find({}, {"_id": 1}):
        await ensure_snapshot_today(str(t["_id"]))
