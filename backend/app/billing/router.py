from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Request, status

import stripe

from app.config import settings
from app.db import tenants
from app.dependencies import CurrentUser, require_lojista

router = APIRouter(prefix="/api/billing", tags=["billing"])

stripe.api_key = settings.stripe_secret_key

DOWNGRADE_STATUSES = {"canceled", "unpaid", "incomplete_expired"}


async def _get_or_create_customer(user: CurrentUser, tenant: dict) -> str:
    if tenant.get("stripe_customer_id"):
        return tenant["stripe_customer_id"]
    customer = stripe.Customer.create(email=user.email, metadata={"tenant_id": user.tenant_id})
    await tenants.update_one(
        {"_id": ObjectId(user.tenant_id)}, {"$set": {"stripe_customer_id": customer.id}}
    )
    return customer.id


@router.post("/checkout")
async def create_checkout_session(user: CurrentUser = Depends(require_lojista)):
    tenant = await tenants.find_one({"_id": ObjectId(user.tenant_id)})
    if not tenant:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Loja não encontrada")

    customer_id = await _get_or_create_customer(user, tenant)

    session = stripe.checkout.Session.create(
        customer=customer_id,
        mode="subscription",
        line_items=[{"price": settings.stripe_full_price_id, "quantity": 1}],
        success_url=f"{settings.frontend_url}/trenddrop-pro.html?billing=success",
        cancel_url=f"{settings.frontend_url}/trenddrop-pro.html?billing=cancel",
        metadata={"tenant_id": user.tenant_id},
    )
    return {"url": session.url}


@router.post("/portal")
async def create_portal_session(user: CurrentUser = Depends(require_lojista)):
    tenant = await tenants.find_one({"_id": ObjectId(user.tenant_id)})
    if not tenant or not tenant.get("stripe_customer_id"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Nenhuma assinatura encontrada pra essa loja")

    portal_session = stripe.billing_portal.Session.create(
        customer=tenant["stripe_customer_id"],
        return_url=f"{settings.frontend_url}/trenddrop-pro.html",
    )
    return {"url": portal_session.url}


@router.post("/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, settings.stripe_webhook_secret)
    except (ValueError, stripe.error.SignatureVerificationError):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Assinatura inválida")

    data = event["data"]["object"].to_dict()
    event_type = event["type"]

    if event_type == "checkout.session.completed":
        tenant_id = data.get("metadata", {}).get("tenant_id")
        if tenant_id:
            await tenants.update_one(
                {"_id": ObjectId(tenant_id)},
                {
                    "$set": {
                        "plan": "full",
                        "stripe_customer_id": data.get("customer"),
                        "stripe_subscription_id": data.get("subscription"),
                    }
                },
            )

    elif event_type in ("customer.subscription.deleted", "customer.subscription.updated"):
        subscription_id = data.get("id")
        new_status = data.get("status")
        if event_type == "customer.subscription.deleted" or new_status in DOWNGRADE_STATUSES:
            await tenants.update_one(
                {"stripe_subscription_id": subscription_id}, {"$set": {"plan": "basico"}}
            )
        elif new_status in ("active", "trialing"):
            await tenants.update_one(
                {"stripe_subscription_id": subscription_id}, {"$set": {"plan": "full"}}
            )

    return {"received": True}
