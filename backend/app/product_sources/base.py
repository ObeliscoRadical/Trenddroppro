from dataclasses import dataclass


class ProviderNotConfigured(Exception):
    pass


@dataclass
class ProductCandidate:
    platform_id: str
    name: str
    category: str
    price: float
    margin: int
    affiliate_url: str
    emoji: str = "📦"


class ProductSource:
    platform_id: str = ""

    def is_configured(self) -> bool:
        raise NotImplementedError

    async def fetch_top_products(self, categories: list[str], limit: int) -> list[ProductCandidate]:
        raise NotImplementedError
