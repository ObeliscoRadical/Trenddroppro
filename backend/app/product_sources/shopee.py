import hashlib
import json
import time

import httpx

from app.config import settings
from app.product_sources.base import ProductCandidate, ProductSource, ProviderNotConfigured

API_URL = "https://open-api.affiliate.shopee.com/graphql"

QUERY = """
query($keyword: String, $limit: Int) {
  productOfferV2(keyword: $keyword, limit: $limit) {
    nodes {
      productName
      price
      commissionRate
      offerLink
      productCatIds
    }
  }
}
"""


def _sign(app_id: str, timestamp: int, payload: str, secret: str) -> str:
    base = f"{app_id}{timestamp}{payload}{secret}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


class ShopeeSource(ProductSource):
    platform_id = "shopee"

    def is_configured(self) -> bool:
        return bool(settings.shopee_app_id and settings.shopee_app_secret)

    async def fetch_top_products(self, categories: list[str], limit: int) -> list[ProductCandidate]:
        if not self.is_configured():
            raise ProviderNotConfigured("Shopee: SHOPEE_APP_ID/SHOPEE_APP_SECRET não configurados")

        candidates: list[ProductCandidate] = []
        search_terms = categories or [""]
        per_category = max(1, limit // max(1, len(search_terms)))

        async with httpx.AsyncClient(timeout=20) as client:
            for term in search_terms:
                if len(candidates) >= limit:
                    break
                variables = {"keyword": term, "limit": min(per_category, 50)}
                body = {"query": QUERY, "variables": variables}
                payload = json.dumps(body, separators=(",", ":"))
                timestamp = int(time.time())
                signature = _sign(settings.shopee_app_id, timestamp, payload, settings.shopee_app_secret)
                headers = {
                    "Authorization": f"SHA256 Credential={settings.shopee_app_id}, Timestamp={timestamp}, Signature={signature}",
                    "Content-Type": "application/json",
                }

                resp = await client.post(API_URL, content=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()

                nodes = data.get("data", {}).get("productOfferV2", {}).get("nodes", [])
                for p in nodes:
                    if len(candidates) >= limit:
                        break
                    try:
                        price = float(p.get("price", 0))
                    except (TypeError, ValueError):
                        price = 0.0
                    try:
                        margin = int(round(float(p.get("commissionRate", 0)) * 100))
                    except (TypeError, ValueError):
                        margin = 0
                    candidates.append(
                        ProductCandidate(
                            platform_id="shopee",
                            name=(p.get("productName") or "Produto Shopee")[:120],
                            category=term or "Geral",
                            price=price,
                            margin=margin,
                            affiliate_url=p.get("offerLink", ""),
                        )
                    )
        return candidates
