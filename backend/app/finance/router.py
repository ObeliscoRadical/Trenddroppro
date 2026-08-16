from datetime import timezone

from fastapi import APIRouter, Depends

from app.db import catalog_products, content_bundles, removal_queue, revenue_snapshots
from app.dependencies import CurrentUser, require_full_plan, require_lojista
from app.finance_snapshots import compute_total_revenue, ensure_snapshot_today
from app.models import ActivityItemOut, FinanceDashboardOut, RevenueByPlatformOut, RevenueHistoryPointOut

router = APIRouter(prefix="/api/finance", tags=["finance"], dependencies=[Depends(require_full_plan)])


def _dt_to_ms(dt) -> int:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


@router.get("/dashboard", response_model=FinanceDashboardOut)
async def finance_dashboard(user: CurrentUser = Depends(require_lojista)):
    await ensure_snapshot_today(user.tenant_id)

    total_revenue = await compute_total_revenue(user.tenant_id)

    fase2_count = await catalog_products.count_documents(
        {"tenant_id": user.tenant_id, "status": "ativo", "fase": "Fase 2"}
    )
    pending_removals = await removal_queue.count_documents({"tenant_id": user.tenant_id})
    approved_bundles = await content_bundles.count_documents(
        {"tenant_id": user.tenant_id, "status": "aprovado"}
    )

    revenue_by_platform: dict[str, float] = {}
    async for p in catalog_products.find(
        {"tenant_id": user.tenant_id, "status": "ativo"}, {"platform": 1, "revenue": 1}
    ):
        revenue_by_platform[p["platform"]] = revenue_by_platform.get(p["platform"], 0) + (p.get("revenue", 0) or 0)
    revenue_by_platform_out = [
        RevenueByPlatformOut(platform=k, revenue=v)
        for k, v in sorted(revenue_by_platform.items(), key=lambda kv: kv[1], reverse=True)
    ]

    history_docs = await revenue_snapshots.find({"tenant_id": user.tenant_id}).sort("date", 1).to_list(length=None)
    revenue_history = [RevenueHistoryPointOut(date=d["date"], totalRevenue=d["totalRevenue"]) for d in history_docs]

    activity: list[ActivityItemOut] = []

    async for p in catalog_products.find({"tenant_id": user.tenant_id}).sort("created_at", -1).limit(5):
        activity.append(ActivityItemOut(
            type="produto", text=f"Produto adicionado ao catálogo — {p['name']}",
            platform=p.get("platform", ""), timestamp=_dt_to_ms(p["created_at"]),
        ))

    async for b in content_bundles.find({"tenant_id": user.tenant_id}).sort("id", -1).limit(5):
        activity.append(ActivityItemOut(
            type="geracao", text=f"Bundle de conteúdo gerado — {b['productName']}",
            platform="", timestamp=b["createdAt"],
        ))

    async for b in content_bundles.find(
        {"tenant_id": user.tenant_id, "approvedAt": {"$ne": None}}
    ).sort("approvedAt", -1).limit(5):
        activity.append(ActivityItemOut(
            type="aprovacao", text=f"Bundle aprovado — {b['productName']}",
            platform="", timestamp=b["approvedAt"],
        ))

    async for r in removal_queue.find({"tenant_id": user.tenant_id}).sort("created_at", -1).limit(5):
        activity.append(ActivityItemOut(
            type="alerta", text=f"Produto sinalizado para revisão — {r['name']}",
            platform=r.get("platform", ""), timestamp=_dt_to_ms(r["created_at"]),
        ))

    activity.sort(key=lambda a: a.timestamp, reverse=True)

    return FinanceDashboardOut(
        totalRevenue=total_revenue,
        fase2Count=fase2_count,
        pendingRemovals=pending_removals,
        approvedBundles=approved_bundles,
        revenueByPlatform=revenue_by_platform_out,
        revenueHistory=revenue_history,
        recentActivity=activity[:8],
    )
