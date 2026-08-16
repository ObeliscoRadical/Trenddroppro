from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


Role = Literal["admin", "lojista"]
Plan = Literal["basico", "full"]


class SignupIn(BaseModel):
    loja: str = Field(min_length=1, max_length=120)
    nome: str = Field(min_length=1, max_length=120)
    email: EmailStr
    senha: str = Field(min_length=8, max_length=72)
    terms_accepted: bool = False


class LoginIn(BaseModel):
    email: EmailStr
    senha: str


class UserOut(BaseModel):
    id: str
    email: EmailStr
    nome: str
    role: Role
    tenant_id: Optional[str] = None
    loja: Optional[str] = None
    auth_method: Literal["email", "google"]
    plan: Plan = "basico"


class TenantDoc(BaseModel):
    nome_loja: str
    status: Literal["active", "suspended"] = "active"
    created_at: datetime = Field(default_factory=utcnow)
    plan: Plan = "basico"
    stripe_customer_id: Optional[str] = None
    stripe_subscription_id: Optional[str] = None


class UserDoc(BaseModel):
    tenant_id: Optional[str] = None
    email: EmailStr
    nome: str
    role: Role
    password_hash: Optional[str] = None
    google_id: Optional[str] = None
    is_active: bool = True
    created_at: datetime = Field(default_factory=utcnow)
    terms_accepted_at: Optional[datetime] = None


class ProductOut(BaseModel):
    id: int
    name: str
    emoji: str
    image: Optional[str] = None
    category: str
    score: int
    demand: int
    competition: str
    margin: int
    trend: str
    trendPct: str
    priceCost: float
    priceSell: float
    tags: list[str]
    description: str
    searchVolume: str
    saturation: int
    platforms: list[str]
    tips: list[str]


class NicheOut(BaseModel):
    id: int
    name: str
    emoji: str
    market: str
    margin: int
    growth: int
    competition: str
    desc: str
    tags: list[str]


class WatchlistAddIn(BaseModel):
    product_id: int


TenantStatus = Literal["active", "suspended"]


class TenantAdminOut(BaseModel):
    id: str
    nome_loja: str
    status: TenantStatus
    created_at: datetime
    owner_nome: Optional[str] = None
    owner_email: Optional[str] = None
    user_count: int


class TenantStatusIn(BaseModel):
    status: TenantStatus


class ScanResultOut(BaseModel):
    product: Optional[ProductOut] = None


class AffiliateConnectionOut(BaseModel):
    platform_id: str
    name: str
    monogram: str
    color: str
    icon: Optional[str] = None
    url: str
    connected: bool
    affiliate_id: Optional[str] = None
    fase: str = "—"
    produtos: int = 0
    receita: str = "R$ 0"


class AffiliateConnectIn(BaseModel):
    affiliate_id: str = Field(min_length=1, max_length=200)


class SocialPageOut(BaseModel):
    page_id: str
    name: str
    has_instagram: bool


class SocialConnectionOut(BaseModel):
    platform: str
    configured: bool
    connected: bool
    pages: list[SocialPageOut] = []
    connected_at: Optional[datetime] = None


CatalogStatus = Literal["ativo", "removido"]
Momentum = Literal["alta", "media", "baixa", "negativa"]


class CatalogProductOut(BaseModel):
    id: int
    name: str
    emoji: str
    platform: str
    category: str
    fase: str
    margin: int
    clicks: int
    revenue: float
    momentum: Momentum
    status: CatalogStatus


class CatalogProductCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    emoji: str = Field(default="📦", max_length=8)
    platform: str = Field(min_length=1, max_length=60)
    category: str = Field(min_length=1, max_length=60)
    fase: str = Field(default="Fase 1", max_length=20)
    margin: int = Field(ge=0, le=100, default=0)
    clicks: int = Field(ge=0, default=0)
    revenue: float = Field(ge=0, default=0)
    momentum: Momentum = "media"


class CatalogProductUpdateIn(BaseModel):
    margin: Optional[int] = Field(default=None, ge=0, le=100)
    clicks: Optional[int] = Field(default=None, ge=0)
    revenue: Optional[float] = Field(default=None, ge=0)
    momentum: Optional[Momentum] = None
    fase: Optional[str] = Field(default=None, max_length=20)


class RemovalMetricsOut(BaseModel):
    cliques: str
    conversao: str


class RemovalQueueItemOut(BaseModel):
    catalog_product_id: int
    name: str
    platform: str
    days: int
    reason: str
    metrics: RemovalMetricsOut
    action: str


class FlagForRemovalIn(BaseModel):
    reason: Optional[str] = None


class ContentHookOut(BaseModel):
    pt: str
    en: str
    score: int
    motivo: str


class ContentTextOut(BaseModel):
    copy: str
    artigo: str
    roteiro: str


class ContentLangBundleOut(BaseModel):
    pt: ContentTextOut
    en: ContentTextOut


BundleStatus = Literal["pendente", "aprovado"]


class ContentBundleOut(BaseModel):
    id: int
    productId: int
    productName: str
    productEmoji: str
    hooks: list[ContentHookOut]
    content: ContentLangBundleOut
    notes: str = ""
    status: BundleStatus
    createdAt: int
    approvedAt: Optional[int] = None


class GenerateContentIn(BaseModel):
    product_id: int


class UpdateBundleIn(BaseModel):
    content: Optional[ContentLangBundleOut] = None
    notes: Optional[str] = None


class BulkApproveIn(BaseModel):
    ids: list[int]


class CommandSettingsOut(BaseModel):
    autonomyOn: bool
    suggestionsPerDay: int
    removalWindow: int
    strictFlag: bool


class CommandSettingsIn(BaseModel):
    autonomyOn: bool
    suggestionsPerDay: int = Field(ge=1, le=20)
    removalWindow: int = Field(ge=1, le=30)
    strictFlag: bool


class RevenueByPlatformOut(BaseModel):
    platform: str
    revenue: float


class RevenueHistoryPointOut(BaseModel):
    date: str
    totalRevenue: float


class ActivityItemOut(BaseModel):
    type: str
    text: str
    platform: str
    timestamp: int


class FinanceDashboardOut(BaseModel):
    totalRevenue: float
    fase2Count: int
    pendingRemovals: int
    approvedBundles: int
    revenueByPlatform: list[RevenueByPlatformOut]
    revenueHistory: list[RevenueHistoryPointOut]
    recentActivity: list[ActivityItemOut]


class OnboardingStepOut(BaseModel):
    id: str
    title: str
    description: str
    done: bool
    view: str
    module: Literal["pesquisa", "afiliados"]


class OnboardingStatusOut(BaseModel):
    steps: list[OnboardingStepOut]
    completed: int
    total: int


class AdminMetricsOut(BaseModel):
    total_lojas: int
    lojas_ativas: int
    lojas_suspensas: int
    novas_ultimos_30_dias: int
