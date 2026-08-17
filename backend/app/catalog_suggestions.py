from datetime import datetime, timezone

from app.db import catalog_products, catalog_suggestions, command_settings, tenants
from app.product_sources.base import ProviderNotConfigured
from app.product_sources.registry import ALL_SOURCES, get_configured_sources

DEFAULT_CATEGORIES = ["Casa", "Beleza", "Eletrônicos", "Fitness", "Pet", "Bebê", "Moda", "Cozinha"]


async def _next_id(collection, tenant_id: str) -> int:
    cursor = collection.find({"tenant_id": tenant_id}, {"id": 1}).sort("id", -1).limit(1)
    docs = await cursor.to_list(length=1)
    return (docs[0]["id"] if docs else 0) + 1


async def run_fetch_for_tenant(tenant_id: str, categories: list[str], limit: int) -> dict:
    settings_doc = await command_settings.find_one({"tenant_id": tenant_id})
    autonomy_on = bool(settings_doc and settings_doc.get("autonomyOn"))

    sources = get_configured_sources()
    skipped = {s.platform_id for s in ALL_SOURCES} - {s.platform_id for s in sources}

    cats = categories or DEFAULT_CATEGORIES
    per_source_limit = max(1, limit // max(1, len(sources))) if sources else 0

    candidates = []
    used = []
    for source in sources:
        try:
            found = await source.fetch_top_products(cats, per_source_limit)
        except ProviderNotConfigured:
            skipped.add(source.platform_id)
            continue
        except Exception:
            skipped.add(source.platform_id)
            continue
        if found:
            used.append(source.platform_id)
            candidates.extend(found)
        if len(candidates) >= limit:
            break
    candidates = candidates[:limit]

    inserted_direct = 0
    now = datetime.now(timezone.utc)

    if autonomy_on:
        next_id = await _next_id(catalog_products, tenant_id)
        docs = []
        for c in candidates:
            docs.append(
                {
                    "tenant_id": tenant_id,
                    "id": next_id,
                    "name": c.name,
                    "emoji": c.emoji,
                    "platform": c.platform_id,
                    "category": c.category,
                    "fase": "Fase 1",
                    "margin": c.margin,
                    "clicks": 0,
                    "revenue": 0.0,
                    "momentum": "media",
                    "status": "ativo",
                    "created_at": now,
                }
            )
            next_id += 1
        if docs:
            await catalog_products.insert_many(docs)
        inserted_direct = len(docs)
    else:
        next_id = await _next_id(catalog_suggestions, tenant_id)
        docs = []
        for c in candidates:
            docs.append(
                {
                    "tenant_id": tenant_id,
                    "id": next_id,
                    "platform_id": c.platform_id,
                    "name": c.name,
                    "emoji": c.emoji,
                    "category": c.category,
                    "price": c.price,
                    "margin": c.margin,
                    "momentum": "media",
                    "affiliate_url": c.affiliate_url,
                    "status": "pendente",
                    "created_at": now,
                }
            )
            next_id += 1
        if docs:
            await catalog_suggestions.insert_many(docs)

    return {
        "mode": "autonomo" if autonomy_on else "fila",
        "fetched": len(candidates),
        "inserted_direct": inserted_direct,
        "sources_used": used,
        "sources_skipped": sorted(skipped),
    }


async def run_daily_suggestions_for_all_tenants() -> None:
    if not get_configured_sources():
        return
    async for tenant in tenants.find({"plan": "full", "status": "active"}, {"_id": 1}):
        tenant_id = str(tenant["_id"])
        settings_doc = await command_settings.find_one({"tenant_id": tenant_id})
        per_day = (settings_doc or {}).get("suggestionsPerDay", 5)
        await run_fetch_for_tenant(tenant_id, [], per_day)
