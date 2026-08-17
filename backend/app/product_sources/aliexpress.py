import hashlib
import time

import httpx

from app.config import settings
from app.product_sources.base import ProductCandidate, ProductSource, ProviderNotConfigured

API_GATEWAY = "https://api-sg.aliexpress.com/sync"


def _sign(params: dict, secret: str) -> str:
    ordered = sorted(params.items())
    base = secret + "".join(f"{k}{v}" for k, v in ordered) + secret
    return hashlib.md5(base.encode("utf-8")).hexdigest().upper()


class AliExpressSource(ProductSource):
    platform_id = "aliexpress"

    def is_configured(self) -> bool:
        return bool(settings.aliexpress_app_key and settings.aliexpress_app_secret and settings.aliexpress_tracking_id)

    async def fetch_top_products(self, categories: list[str], limit: int) -> list[ProductCandidate]:
        if not self.is_configured():
            raise ProviderNotConfigured("AliExpress: ALIEXPRESS_APP_KEY/SECRET/TRACKING_ID não configurados")

        candidates: list[ProductCandidate] = []
        per_category = max(1, limit // max(1, len(categories))) if categories else limit
        search_terms = categories or [""]

        async with httpx.AsyncClient(timeout=20) as client:
            for term in search_terms:
                if len(candidates) >= limit:
                    break
                params = {
                    "app_key": settings.aliexpress_app_key,
                    "method": "aliexpress.affiliate.hotproduct.query",
                    "timestamp": str(int(time.time() * 1000)),
                    "sign_method": "md5",
                    "v": "2.0",
                    "format": "json",
                    "tracking_id": settings.aliexpress_tracking_id,
                    "page_size": str(min(per_category, 50)),
                    "page_no": "1",
                    "target_currency": "EUR",
                    "target_language": "PT",
                    "ship_to_country": "PT",
                }
                if term:
                    params["keywords"] = term
                params["sign"] = _sign(params, settings.aliexpress_app_secret)

                resp = await client.get(API_GATEWAY, params=params)
                resp.raise_for_status()
                data = resp.json()

                result = (
                    data.get("aliexpress_affiliate_hotproduct_query_response", {})
                    .get("resp_result", {})
                    .get("result", {})
                )
                products = result.get("products", {}).get("product", [])
                for p in products:
                    if len(candidates) >= limit:
                        break
                    try:
                        price = float(p.get("target_sale_price") or p.get("sale_price") or 0)
                    except (TypeError, ValueError):
                        price = 0.0
                    margin_raw = p.get("commission_rate") or p.get("hot_product_commission_rate") or "0"
                    try:
                        margin = int(round(float(str(margin_raw).replace("%", ""))))
                    except (TypeError, ValueError):
                        margin = 0
                    candidates.append(
                        ProductCandidate(
                            platform_id="aliexpress",
                            name=p.get("product_title", "Produto AliExpress")[:120],
                            category=term or p.get("first_level_category_name", "Geral"),
                            price=price,
                            margin=margin,
                            affiliate_url=p.get("promotion_link", p.get("product_detail_url", "")),
                        )
                    )
        return candidates
