import httpx

from app.config import settings
from app.product_sources.base import ProductCandidate, ProductSource, ProviderNotConfigured

API_BASE = "https://api.awin.com"


class AwinSource(ProductSource):
    platform_id = "awin"

    def is_configured(self) -> bool:
        return bool(settings.awin_api_token and settings.awin_publisher_id)

    async def fetch_top_products(self, categories: list[str], limit: int) -> list[ProductCandidate]:
        if not self.is_configured():
            raise ProviderNotConfigured("Awin: AWIN_API_TOKEN/AWIN_PUBLISHER_ID não configurados")

        candidates: list[ProductCandidate] = []
        headers = {"Authorization": f"Bearer {settings.awin_api_token}"}
        search_terms = categories or [""]
        per_category = max(1, limit // max(1, len(search_terms)))

        async with httpx.AsyncClient(timeout=20, headers=headers) as client:
            for term in search_terms:
                if len(candidates) >= limit:
                    break
                params = {"limit": min(per_category, 50)}
                if term:
                    params["query"] = term

                resp = await client.get(
                    f"{API_BASE}/publishers/{settings.awin_publisher_id}/product-search", params=params
                )
                resp.raise_for_status()
                data = resp.json()

                for p in data.get("products", []):
                    if len(candidates) >= limit:
                        break
                    try:
                        price = float(p.get("displayPrice", {}).get("amount", 0))
                    except (TypeError, ValueError, AttributeError):
                        price = 0.0
                    try:
                        margin = int(round(float(p.get("commissionRange", {}).get("max", 0))))
                    except (TypeError, ValueError, AttributeError):
                        margin = 0
                    candidates.append(
                        ProductCandidate(
                            platform_id="awin",
                            name=(p.get("productName") or "Produto Awin")[:120],
                            category=term or p.get("categoryName", "Geral"),
                            price=price,
                            margin=margin,
                            affiliate_url=p.get("awTrackingUrl", p.get("productUrl", "")),
                        )
                    )
        return candidates
