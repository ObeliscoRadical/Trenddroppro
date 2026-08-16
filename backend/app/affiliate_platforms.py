AFFILIATE_PLATFORMS = [
    {"platform_id": "amazon", "name": "Amazon Associados", "monogram": "A", "color": "#FF9900", "icon": "fa-brands fa-amazon", "url": "https://associados.amazon.com.br"},
    {"platform_id": "aliexpress", "name": "AliExpress Affiliate", "monogram": "Ali", "color": "#E62E04", "icon": None, "url": "https://portals.aliexpress.com"},
    {"platform_id": "shopee", "name": "Shopee Afiliados", "monogram": "S", "color": "#EE4D2D", "icon": "fa-solid fa-bag-shopping", "url": "https://affiliate.shopee.com.br"},
    {"platform_id": "awin", "name": "Awin", "monogram": "Aw", "color": "#00B3A4", "icon": None, "url": "https://www.awin.com"},
    {"platform_id": "rakuten", "name": "Rakuten Advertising", "monogram": "R", "color": "#BF0000", "icon": None, "url": "https://rakutenadvertising.com"},
    {"platform_id": "kiwify", "name": "Kiwify", "monogram": "K", "color": "#04D9B2", "icon": "fa-solid fa-play", "url": "https://kiwify.com.br"},
]

AFFILIATE_PLATFORM_IDS = {p["platform_id"] for p in AFFILIATE_PLATFORMS}
