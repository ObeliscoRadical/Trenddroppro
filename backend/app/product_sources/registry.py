from app.product_sources.aliexpress import AliExpressSource
from app.product_sources.amazon import AmazonSource
from app.product_sources.awin import AwinSource
from app.product_sources.base import ProductSource
from app.product_sources.kiwify import KiwifySource
from app.product_sources.rakuten import RakutenSource
from app.product_sources.shopee import ShopeeSource

ALL_SOURCES: list[ProductSource] = [
    AliExpressSource(),
    AwinSource(),
    AmazonSource(),
    RakutenSource(),
    ShopeeSource(),
    KiwifySource(),
]


def get_configured_sources() -> list[ProductSource]:
    return [s for s in ALL_SOURCES if s.is_configured()]


def sources_status() -> list[dict]:
    return [{"platform_id": s.platform_id, "configured": s.is_configured()} for s in ALL_SOURCES]
