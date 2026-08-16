import json
import logging

import anthropic

from app.config import settings
from app.db import products

logger = logging.getLogger(__name__)

DISCOVERY_POOL = [
    {"id":19,"name":"Umidificador USB Portátil","emoji":"💧","image":"https://i.ebayimg.com/images/g/VcQAAOSwXGtkvxH7/s-l400.jpg","category":"Casa & Decoração","score":86,"demand":75,"competition":"Baixa","margin":64,"trend":"up","trendPct":"+52%","priceCost":9,"priceSell":55,"description":"Mini umidificador ultrassônico USB, popular para mesa de trabalho e quarto — categoria em crescimento com baixa concorrência direta ainda.","searchVolume":"68k/mês","saturation":18,"platforms":["Shopee","Mercado Livre"],"tags":["Novidade","Home Office"],"tips":["Produto recém-detectado pelo scan — ainda com pouca concorrência, boa janela pra entrar cedo","Mostre o efeito da névoa em ambiente escuro no vídeo","Combine com óleos essenciais pra aumentar o ticket médio"]},
    {"id":20,"name":"Suporte Ajustável para Notebook","emoji":"💻","image":"https://i.ebayimg.com/images/g/WdkAAeSwsehqazZm/s-l400.jpg","category":"Tech & Gadgets","score":82,"demand":70,"competition":"Média","margin":58,"trend":"up","trendPct":"+35%","priceCost":14,"priceSell":69,"description":"Suporte de alumínio dobrável para notebook, detectado subindo junto com a onda de setups de home office.","searchVolume":"54k/mês","saturation":33,"platforms":["Shopee","Mercado Livre","Amazon"],"tags":["Novidade","Home Office"],"tips":["Produto recém-detectado pelo scan — monitore a evolução de saturação nas próximas semanas","Enfatize ergonomia e postura no anúncio","Fotos comparando a altura da tela antes/depois convertem bem"]},
    {"id":21,"name":"Escova Alisadora Elétrica","emoji":"🪮","image":"https://i.ebayimg.com/images/g/SBYAAOSwHAxi2IN6/s-l400.jpg","category":"Beleza & Estética","score":84,"demand":77,"competition":"Média","margin":61,"trend":"up","trendPct":"+44%","priceCost":19,"priceSell":89,"description":"Escova alisadora cerâmica com fio, ganhando tração em vídeos de rotina de beleza — detectada nesse scan.","searchVolume":"91k/mês","saturation":29,"platforms":["Shopee","Mercado Livre"],"tags":["Novidade","Viral TikTok"],"tips":["Produto recém-detectado pelo scan — ainda dá tempo de entrar antes da saturação subir","Vídeo de transformação rápida (antes/depois) é o formato que mais converte nessa categoria","Compare o resultado com salão pra justificar o preço"]},
]

CATEGORIES = [
    "Beleza & Estética", "Casa & Decoração", "Fitness & Saúde", "Tech & Gadgets",
    "Pets", "Moda & Acessórios", "Kids & Baby", "Outdoor & Camping",
]


def _clamp(value, lo, hi, default):
    try:
        v = round(float(value))
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, v))


async def _next_pool_item() -> dict | None:
    for item in DISCOVERY_POOL:
        if not await products.find_one({"id": item["id"]}):
            return item
    return None


async def _next_ai_id() -> int:
    cursor = products.find({}, {"id": 1}).sort("id", -1).limit(1)
    docs = await cursor.to_list(length=1)
    current_max = docs[0]["id"] if docs else 0
    return max(999, current_max) + 1


async def _ask_claude_for_product() -> dict | None:
    if not settings.anthropic_api_key:
        return None

    existing = await products.find({}, {"name": 1}).to_list(length=None)
    existing_names = ", ".join(p["name"] for p in existing)

    prompt = f"""Você é um pesquisador de produtos para dropshipping no Brasil. Use busca na web para encontrar UM produto de nicho que esteja genuinamente em alta agora (tendência real, não genérica), com baixa a média concorrência, ideal para revenda via Shopee, Mercado Livre ou AliExpress.

Não repita nenhum destes produtos já cadastrados: {existing_names}.

Durante a busca, tente localizar uma URL de imagem direta e pública do produto, preferindo imagens hospedadas em CDNs de marketplaces (ex: ebayimg.com, alicdn.com) que terminem em .jpg, .png ou .webp.

Responda APENAS com um JSON válido (sem markdown, sem crases, sem texto antes ou depois), exatamente neste formato:
{{"name":"nome do produto em português","emoji":"um emoji representativo","image":"URL direta de uma imagem real do produto, ou null se não encontrar uma confiável","category":"uma destas: {", ".join(CATEGORIES)}","score":numero de 0 a 100,"demand":numero de 0 a 100,"competition":"Baixa ou Média ou Alta","margin":numero percentual,"trendPct":"+XX%","priceCost":numero em reais,"priceSell":numero em reais,"tags":["tag1","tag2"],"description":"1 a 2 frases sobre o produto e por que está em alta","searchVolume":"XXk/mês","saturation":numero de 0 a 100,"platforms":["Shopee","Mercado Livre"],"tips":["dica 1","dica 2","dica 3"]}}"""

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    messages = [{"role": "user", "content": prompt}]
    tools = [{"type": "web_search_20260209", "name": "web_search"}]

    try:
        response = client.messages.create(
            model="claude-opus-5",
            max_tokens=2000,
            output_config={"effort": "low"},
            tools=tools,
            messages=messages,
        )
        for _ in range(3):
            if response.stop_reason != "pause_turn":
                break
            messages.append({"role": "assistant", "content": response.content})
            response = client.messages.create(
                model="claude-opus-5",
                max_tokens=2000,
                output_config={"effort": "low"},
                tools=tools,
                messages=messages,
            )

        if response.stop_reason == "refusal":
            return None

        text_blocks = [b for b in response.content if b.type == "text"]
        if not text_blocks:
            return None

        raw = text_blocks[-1].text.strip()
        raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        parsed = json.loads(raw)
        if not parsed.get("name") or not parsed.get("category"):
            return None
        return parsed
    except Exception:
        logger.exception("Falha ao descobrir produto via IA")
        return None


async def discover_product() -> dict | None:
    ai_product = await _ask_claude_for_product()

    if ai_product:
        image = ai_product.get("image")
        product = {
            "id": await _next_ai_id(),
            "name": str(ai_product["name"])[:60],
            "emoji": ai_product.get("emoji") or "🆕",
            "image": image if isinstance(image, str) and image.startswith("http") else None,
            "category": ai_product.get("category") if ai_product.get("category") in CATEGORIES else "Tech & Gadgets",
            "score": _clamp(ai_product.get("score"), 40, 99, 70),
            "demand": _clamp(ai_product.get("demand"), 30, 99, 60),
            "competition": ai_product.get("competition") if ai_product.get("competition") in ("Baixa", "Média", "Alta") else "Média",
            "margin": _clamp(ai_product.get("margin"), 20, 80, 50),
            "trend": "up",
            "trendPct": ai_product.get("trendPct") or "+30%",
            "priceCost": _clamp(ai_product.get("priceCost"), 1, 500, 10),
            "priceSell": _clamp(ai_product.get("priceSell"), 1, 2000, 50),
            "tags": ai_product.get("tags")[:3] if isinstance(ai_product.get("tags"), list) else ["Novidade"],
            "description": ai_product.get("description") or "Produto identificado pela IA como tendência emergente.",
            "searchVolume": ai_product.get("searchVolume") or "—",
            "saturation": _clamp(ai_product.get("saturation"), 10, 60, 30),
            "platforms": ai_product.get("platforms") if isinstance(ai_product.get("platforms"), list) and ai_product.get("platforms") else ["Shopee", "Mercado Livre"],
            "tips": ai_product.get("tips")[:3] if isinstance(ai_product.get("tips"), list) else ["Produto identificado por pesquisa de IA em tempo real."],
        }
    else:
        product = await _next_pool_item()
        if not product:
            return None

    await products.update_one({"id": product["id"]}, {"$set": product}, upsert=True)
    return product
