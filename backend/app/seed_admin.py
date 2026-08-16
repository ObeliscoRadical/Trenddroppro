import asyncio
import sys
from datetime import datetime, timezone

from app.config import settings
from app.db import ensure_indexes, users
from app.security import hash_password


async def seed_admin() -> None:
    if not settings.seed_admin_email or not settings.seed_admin_password:
        print("Defina SEED_ADMIN_EMAIL e SEED_ADMIN_PASSWORD no .env antes de rodar este script.")
        sys.exit(1)

    await ensure_indexes()

    await users.update_one(
        {"email": settings.seed_admin_email},
        {
            "$set": {
                "email": settings.seed_admin_email,
                "nome": settings.seed_admin_nome,
                "role": "admin",
                "tenant_id": None,
                "password_hash": hash_password(settings.seed_admin_password),
                "is_active": True,
            },
            "$setOnInsert": {"google_id": None, "created_at": datetime.now(timezone.utc)},
        },
        upsert=True,
    )
    print(f"Admin pronto: {settings.seed_admin_email}")


if __name__ == "__main__":
    asyncio.run(seed_admin())
