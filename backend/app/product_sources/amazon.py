import hashlib
import hmac
import json
from datetime import datetime, timezone

import httpx

from app.config import settings
from app.product_sources.base import ProductCandidate, ProductSource, ProviderNotConfigured

SERVICE = "ProductAdvertisingAPI"
TARGET = "com.amazon.paapi5.v1.ProductAdvertisingAPIv1.SearchItems"
PATH = "/paapi5/searchitems"


def _hmac(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def _sign_request(host: str, region: str, body: str, amz_date: str) -> str:
    date_stamp = amz_date[:8]
    canonical_headers = (
        f"content-encoding:amz-1.0\n"
        f"content-type:application/json; charset=utf-8\n"
        f"host:{host}\n"
        f"x-amz-date:{amz_date}\n"
        f"x-amz-target:{TARGET}\n"
    )
    signed_headers = "content-encoding;content-type;host;x-amz-date;x-amz-target"
    payload_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()
    canonical_request = f"POST\n{PATH}\n\n{canonical_headers}\n{signed_headers}\n{payload_hash}"

    credential_scope = f"{date_stamp}/{region}/{SERVICE}/aws4_request"
    string_to_sign = (
        f"AWS4-HMAC-SHA256\n{amz_date}\n{credential_scope}\n"
        f"{hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()}"
    )

    k_date = _hmac(f"AWS4{settings.amazon_pa_api_secret_key}".encode("utf-8"), date_stamp)
    k_region = _hmac(k_date, region)
    k_service = _hmac(k_region, SERVICE)
    k_signing = _hmac(k_service, "aws4_request")
    signature = hmac.new(k_signing, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

    return (
        f"AWS4-HMAC-SHA256 Credential={settings.amazon_pa_api_access_key}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )


class AmazonSource(ProductSource):
    platform_id = "amazon"

    def is_configured(self) -> bool:
        return bool(
            settings.amazon_pa_api_access_key
            and settings.amazon_pa_api_secret_key
            and settings.amazon_pa_api_partner_tag
        )

    async def fetch_top_products(self, categories: list[str], limit: int) -> list[ProductCandidate]:
        if not self.is_configured():
            raise ProviderNotConfigured("Amazon: credenciais da PA-API não configuradas")

        host = settings.amazon_pa_api_host
        region = settings.amazon_pa_api_region
        marketplace = f"www.{host.split('webservices.', 1)[-1]}"

        candidates: list[ProductCandidate] = []
        search_terms = categories or ["mais vendidos"]
        per_category = min(10, max(1, limit // max(1, len(search_terms))))

        async with httpx.AsyncClient(timeout=20) as client:
            for term in search_terms:
                if len(candidates) >= limit:
                    break
                amz_date = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                payload = {
                    "Keywords": term,
                    "PartnerTag": settings.amazon_pa_api_partner_tag,
                    "PartnerType": "Associates",
                    "Marketplace": marketplace,
                    "SearchIndex": "All",
                    "ItemCount": per_category,
                    "Resources": [
                        "ItemInfo.Title",
                        "Offers.Listings.Price",
                        "BrowseNodeInfo.BrowseNodes",
                    ],
                }
                body = json.dumps(payload)
                authorization = _sign_request(host, region, body, amz_date)
                headers = {
                    "content-encoding": "amz-1.0",
                    "content-type": "application/json; charset=utf-8",
                    "host": host,
                    "x-amz-date": amz_date,
                    "x-amz-target": TARGET,
                    "Authorization": authorization,
                }

                resp = await client.post(f"https://{host}{PATH}", content=body, headers=headers)
                resp.raise_for_status()
                data = resp.json()

                for item in data.get("SearchResult", {}).get("Items", []):
                    if len(candidates) >= limit:
                        break
                    title = item.get("ItemInfo", {}).get("Title", {}).get("DisplayValue", "Produto Amazon")
                    listings = item.get("Offers", {}).get("Listings", [])
                    price = 0.0
                    if listings:
                        price = float(listings[0].get("Price", {}).get("Amount", 0))
                    nodes = item.get("BrowseNodeInfo", {}).get("BrowseNodes", [])
                    category = nodes[0].get("DisplayName", term) if nodes else term
                    candidates.append(
                        ProductCandidate(
                            platform_id="amazon",
                            name=title[:120],
                            category=category,
                            price=price,
                            margin=0,
                            affiliate_url=item.get("DetailPageURL", ""),
                        )
                    )
        return candidates
