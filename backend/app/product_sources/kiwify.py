import httpx

from app.config import settings
from app.product_sources.base import ProductCandidate, ProductSource, ProviderNotConfigured

API_BASE = "https://public-api.kiwify.com/v1"


class KiwifySource(ProductSource):
    platform_id = "kiwify"

    def is_configured(self) -> bool:
        return bool(settings.kiwify_api_token and settings.kiwify_account_id)

    async def fetch_top_products(self, categories: list[str], limit: int) -> list[ProductCandidate]:
        if not self.is_configured():
            raise ProviderNotConfigured("Kiwify: KIWIFY_API_TOKEN/KIWIFY_ACCOUNT_ID não configurados")

        candidates: list[ProductCandidate] = []
        headers = {
            "Authorization": f"Bearer {settings.kiwify_api_token}",
            "x-kiwify-account-id": settings.kiwify_account_id,
        }
        search_terms = categories or [""]
        per_category = max(1, limit // max(1, len(search_terms)))

        async with httpx.AsyncClient(timeout=20, headers=headers) as client:
            for term in search_terms:
                if len(candidates) >= limit:
                    break
                params = {"limit": min(per_category, 50)}
                if term:
                    params["category"] = term

                resp = await client.get(f"{API_BASE}/marketplace/products", params=params)
                resp.raise_for_status()
                data = resp.json()

                for p in data.get("data", []):
                    if len(candidates) >= limit:
                        break
                    try:
                        price = float(p.get("price", 0))
                    except (TypeError, ValueError):
                        price = 0.0
                    try:
                        margin = int(round(float(p.get("commission_percentage", 0))))
                    except (TypeError, ValueError):
                        margin = 0
                    candidates.append(
                        ProductCandidate(
                            platform_id="kiwify",
                            name=(p.get("name") or "Produto Kiwify")[:120],
                            category=term or p.get("category", "Infoproduto"),
                            price=price,
                            margin=margin,
                            affiliate_url=p.get("affiliate_link", ""),
                        )
                    )
        return candidates
