import certifi
from motor.motor_asyncio import AsyncIOMotorClient

from app.config import settings

client = AsyncIOMotorClient(settings.mongodb_uri, tlsCAFile=certifi.where())
db = client[settings.mongodb_db_name]

tenants = db["tenants"]
users = db["users"]
refresh_tokens = db["refresh_tokens"]
products = db["products"]
niches = db["niches"]
watchlist = db["watchlist"]
affiliate_connections = db["affiliate_connections"]
social_connections = db["social_connections"]
catalog_products = db["catalog_products"]
removal_queue = db["removal_queue"]
content_bundles = db["content_bundles"]
command_settings = db["command_settings"]
revenue_snapshots = db["revenue_snapshots"]
scan_usage = db["scan_usage"]


async def ensure_indexes():
    await users.create_index("email", unique=True)
    await users.create_index("google_id", sparse=True)
    await refresh_tokens.create_index("token_hash", unique=True)
    await refresh_tokens.create_index("expires_at", expireAfterSeconds=0)
    await products.create_index("id", unique=True)
    await niches.create_index("id", unique=True)
    await watchlist.create_index([("tenant_id", 1), ("product_id", 1)], unique=True)
    await affiliate_connections.create_index([("tenant_id", 1), ("platform_id", 1)], unique=True)
    await social_connections.create_index([("tenant_id", 1), ("platform", 1)], unique=True)
    await catalog_products.create_index([("tenant_id", 1), ("id", 1)], unique=True)
    await removal_queue.create_index([("tenant_id", 1), ("catalog_product_id", 1)], unique=True)
    await content_bundles.create_index([("tenant_id", 1), ("id", 1)], unique=True)
    await command_settings.create_index("tenant_id", unique=True)
    await revenue_snapshots.create_index([("tenant_id", 1), ("date", 1)], unique=True)
    await scan_usage.create_index([("tenant_id", 1), ("date", 1)], unique=True)
