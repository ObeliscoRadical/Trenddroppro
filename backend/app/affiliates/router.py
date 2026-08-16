from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status

from app.affiliate_platforms import AFFILIATE_PLATFORM_IDS, AFFILIATE_PLATFORMS
from app.db import affiliate_connections
from app.dependencies import CurrentUser, require_full_plan, require_lojista
from app.models import AffiliateConnectIn, AffiliateConnectionOut

router = APIRouter(prefix="/api/affiliates", tags=["affiliates"], dependencies=[Depends(require_full_plan)])


async def _connections_by_platform(tenant_id: str) -> dict[str, dict]:
    docs = await affiliate_connections.find({"tenant_id": tenant_id}).to_list(length=None)
    return {d["platform_id"]: d for d in docs}


def _build_out(platform: dict, conn: dict | None) -> AffiliateConnectionOut:
    return AffiliateConnectionOut(
        platform_id=platform["platform_id"],
        name=platform["name"],
        monogram=platform["monogram"],
        color=platform["color"],
        icon=platform["icon"],
        url=platform["url"],
        connected=bool(conn and conn.get("connected")),
        affiliate_id=conn.get("affiliate_id") if conn else None,
    )


@router.get("", response_model=list[AffiliateConnectionOut])
async def list_affiliate_connections(user: CurrentUser = Depends(require_lojista)):
    connections = await _connections_by_platform(user.tenant_id)
    return [_build_out(p, connections.get(p["platform_id"])) for p in AFFILIATE_PLATFORMS]


@router.post("/{platform_id}/connect", response_model=AffiliateConnectionOut)
async def connect_affiliate_platform(
    platform_id: str, data: AffiliateConnectIn, user: CurrentUser = Depends(require_lojista)
):
    if platform_id not in AFFILIATE_PLATFORM_IDS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Plataforma não encontrada")

    await affiliate_connections.update_one(
        {"tenant_id": user.tenant_id, "platform_id": platform_id},
        {
            "$set": {
                "connected": True,
                "affiliate_id": data.affiliate_id,
                "connected_at": datetime.now(timezone.utc),
            }
        },
        upsert=True,
    )

    platform = next(p for p in AFFILIATE_PLATFORMS if p["platform_id"] == platform_id)
    conn = await affiliate_connections.find_one({"tenant_id": user.tenant_id, "platform_id": platform_id})
    return _build_out(platform, conn)


@router.post("/{platform_id}/disconnect", response_model=AffiliateConnectionOut)
async def disconnect_affiliate_platform(platform_id: str, user: CurrentUser = Depends(require_lojista)):
    if platform_id not in AFFILIATE_PLATFORM_IDS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Plataforma não encontrada")

    await affiliate_connections.update_one(
        {"tenant_id": user.tenant_id, "platform_id": platform_id},
        {"$set": {"connected": False}},
    )

    platform = next(p for p in AFFILIATE_PLATFORMS if p["platform_id"] == platform_id)
    conn = await affiliate_connections.find_one({"tenant_id": user.tenant_id, "platform_id": platform_id})
    return _build_out(platform, conn)
