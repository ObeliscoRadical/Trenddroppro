import sys

import stripe

from app.config import settings

PRODUCT_NAME = "TrendDrop PRO — Full"
PRICE_EUR_CENTS = 2900  # €29,00/mês — placeholder, ajuste no Stripe Dashboard quando decidir o preço final


def seed_billing() -> None:
    if not settings.stripe_secret_key:
        print("Defina STRIPE_SECRET_KEY no .env antes de rodar este script.")
        sys.exit(1)

    stripe.api_key = settings.stripe_secret_key

    for price in stripe.Price.list(active=True, limit=100).auto_paging_iter():
        if not price.recurring or price.recurring.interval != "month":
            continue
        product = stripe.Product.retrieve(price.product)
        if product.name == PRODUCT_NAME:
            print(f"Já existe: price_id={price.id}")
            print("Coloque isso em STRIPE_FULL_PRICE_ID no .env")
            return

    product = stripe.Product.create(name=PRODUCT_NAME)
    price = stripe.Price.create(
        product=product.id,
        unit_amount=PRICE_EUR_CENTS,
        currency="eur",
        recurring={"interval": "month"},
    )
    print(f"Criado: price_id={price.id}")
    print("Coloque isso em STRIPE_FULL_PRICE_ID no .env")


if __name__ == "__main__":
    seed_billing()
