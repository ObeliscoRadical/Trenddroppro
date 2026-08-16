from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.admin import router as admin_router
from app.affiliates import router as affiliates_router
from app.auth import google, router as auth_router
from app.billing import router as billing_router
from app.catalog import router as catalog_router
from app.catalog_ops import router as catalog_ops_router
from app.command import router as command_router
from app.config import settings
from app.content import router as content_router
from app.db import ensure_indexes
from app.finance import router as finance_router
from app.finance_snapshots import snapshot_all_tenants
from app.onboarding import router as onboarding_router
from app.social import router as social_router
from app.watchlist import router as watchlist_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await ensure_indexes()

    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(snapshot_all_tenants, "cron", hour=3, minute=0, id="daily_revenue_snapshot")
    scheduler.start()
    await snapshot_all_tenants()

    yield

    scheduler.shutdown()


app = FastAPI(title="TrendDrop PRO API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router.router)
app.include_router(google.router)
app.include_router(catalog_router.router)
app.include_router(watchlist_router.router)
app.include_router(admin_router.router)
app.include_router(affiliates_router.router)
app.include_router(social_router.router)
app.include_router(catalog_ops_router.router)
app.include_router(content_router.router)
app.include_router(command_router.router)
app.include_router(finance_router.router)
app.include_router(onboarding_router.router)
app.include_router(billing_router.router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
