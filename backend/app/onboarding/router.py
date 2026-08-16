from fastapi import APIRouter, Depends

from app.db import affiliate_connections, catalog_products, content_bundles, social_connections, watchlist
from app.dependencies import CurrentUser, require_lojista
from app.models import OnboardingStatusOut, OnboardingStepOut

router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])

STEP_DEFS = [
    {
        "id": "research",
        "title": "Descubra um produto",
        "description": "Rode o Scan de Tendências ou salve um produto na Watchlist.",
        "view": "dashboard",
        "module": "pesquisa",
    },
    {
        "id": "affiliate_platform",
        "title": "Conecte uma plataforma de afiliados",
        "description": "Amazon, AliExpress, Shopee ou outra — no Hub de Afiliações.",
        "view": "aff-hub",
        "module": "afiliados",
    },
    {
        "id": "catalog_product",
        "title": "Adicione um produto ao Catálogo Dinâmico",
        "description": "É o produto que você vai promover como afiliado.",
        "view": "catalogo",
        "module": "afiliados",
    },
    {
        "id": "content_generated",
        "title": "Gere conteúdo com IA",
        "description": "Hooks, copy, artigo SEO e roteiro pro produto do catálogo.",
        "view": "geracao",
        "module": "afiliados",
    },
    {
        "id": "content_approved",
        "title": "Aprove o conteúdo gerado",
        "description": "Revise e aprove antes de publicar.",
        "view": "revisao",
        "module": "afiliados",
    },
    {
        "id": "social_connected",
        "title": "Conecte sua conta do Instagram/Facebook",
        "description": "Pra ter onde publicar o conteúdo aprovado.",
        "view": "contas",
        "module": "afiliados",
    },
]


@router.get("/status", response_model=OnboardingStatusOut)
async def onboarding_status(user: CurrentUser = Depends(require_lojista)):
    tenant_id = user.tenant_id

    has_watchlist = await watchlist.count_documents({"tenant_id": tenant_id}) > 0
    has_affiliate = await affiliate_connections.count_documents({"tenant_id": tenant_id, "connected": True}) > 0
    has_catalog_product = await catalog_products.count_documents({"tenant_id": tenant_id, "status": "ativo"}) > 0
    has_bundle = await content_bundles.count_documents({"tenant_id": tenant_id}) > 0
    has_approved_bundle = await content_bundles.count_documents({"tenant_id": tenant_id, "status": "aprovado"}) > 0
    has_social = await social_connections.count_documents(
        {"tenant_id": tenant_id, "platform": "meta", "connected": True}
    ) > 0

    done_by_id = {
        "research": has_watchlist,
        "affiliate_platform": has_affiliate,
        "catalog_product": has_catalog_product,
        "content_generated": has_bundle,
        "content_approved": has_approved_bundle,
        "social_connected": has_social,
    }

    steps = [OnboardingStepOut(**s, done=done_by_id[s["id"]]) for s in STEP_DEFS]
    completed = sum(1 for s in steps if s.done)

    return OnboardingStatusOut(steps=steps, completed=completed, total=len(steps))
