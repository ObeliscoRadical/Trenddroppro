import httpx

from app.config import settings
from app.product_sources.base import ProductCandidate, ProductSource, ProviderNotConfigured

API_BASE = "https://api.linksynergy.com/productsearch/1.0"


class RakutenSource(ProductSource):
    platform_id = "rakuten"

    def is_configured(self) -> bool:
        return bool(settings.rakuten_api_token)

    async def fetch_top_products(self, categories: list[str], limit: int) -> list[ProductCandidate]:
        if not self.is_configured():
            raise ProviderNotConfigured("Rakuten: RAKUTEN_API_TOKEN não configurado")

        candidates: list[ProductCandidate] = []
        headers = {"Authorization": f"Bearer {settings.rakuten_api_token}"}
        search_terms = categories or [""]
        per_category = max(1, limit // max(1, len(search_terms)))

        async with httpx.AsyncClient(timeout=20, headers=headers) as client:
            for term in search_terms:
                if len(candidates) >= limit:
                    break
                params = {"max": min(per_category, 50)}
                if settings.rakuten_site_id:
                    params["mid"] = settings.rakuten_site_id
                if term:
                    params["keyword"] = term

                resp = await client.get(API_BASE, params=params)
                resp.raise_for_status()
                data = resp.json()

                items = data.get("item", []) if isinstance(data, dict) else []
                for p in items:
                    if len(candidates) >= limit:
                        break
                    try:
                        price = float(p.get("price", 0))
                    except (TypeError, ValueError):
                        price = 0.0
                    try:
                        margin = int(round(float(str(p.get("commissionrate", 0)).replace("%", ""))))
                    except (TypeError, ValueError):
                        margin = 0
                    candidates.append(
                        ProductCandidate(
                            platform_id="rakuten",
                            name=(p.get("productname") or "Produto Rakuten")[:120],
                            category=term or p.get("category", {}).get("primary", "Geral"),
                            price=price,
                            margin=margin,
                            affiliate_url=p.get("linkurl", ""),
                        )
                    )
        return candidates
