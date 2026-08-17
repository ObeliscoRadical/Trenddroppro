import json

import anthropic

from app.config import settings


class ContentGenerationError(Exception):
    pass


MAX_ATTEMPTS = 3


def _build_prompt(product: dict) -> str:
    return f"""Você é um redator especialista em marketing de afiliados no Brasil. Gere conteúdo promocional para o produto abaixo.

Produto: {product['name']}
Categoria: {product['category']}
Plataforma de afiliados: {product['platform']}
Margem: {product['margin']}%

Responda APENAS com um JSON válido (sem markdown, sem crases, sem texto antes ou depois), exatamente neste formato:
{{"hooks":[{{"pt":"hook curto e chamativo em português, no máximo 15 palavras","en":"tradução para inglês","score":numero de 0 a 100 representando força estimada de conversão,"motivo":"por que esse hook funciona, em 1 frase curta"}}],"content":{{"pt":{{"copy":"copy de vendas curto, 2 a 3 frases, tom persuasivo","artigo":"mini artigo SEO: um título seguido de 2 parágrafos curtos","roteiro":"roteiro de vídeo curto de 15 a 30 segundos, em 4 a 5 linhas indicando cena e fala"}},"en":{{"copy":"same as above in English","artigo":"same in English","roteiro":"same in English"}}}}}}

O array "hooks" deve ter exatamente 3 itens, ordenados do maior score para o menor. Seja direto e conciso — cada campo de texto deve ter no máximo 3 a 4 frases curtas."""


def _request_bundle(client: anthropic.Anthropic, prompt: str) -> dict:
    response = client.messages.create(
        model="claude-opus-5",
        max_tokens=2000,
        output_config={"effort": "low"},
        messages=[{"role": "user", "content": prompt}],
    )
    text_blocks = [b for b in response.content if b.type == "text"]
    if not text_blocks:
        raise ContentGenerationError("Resposta da IA sem texto")

    raw = text_blocks[-1].text.strip()
    raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    parsed = json.loads(raw)

    hooks = [h for h in parsed["hooks"] if h.get("pt") and h.get("en")]
    content = parsed["content"]
    if len(hooks) < 3 or "pt" not in content or "en" not in content:
        raise ContentGenerationError("JSON da IA incompleto")
    return {"hooks": hooks[:3], "content": content}


async def generate_bundle(product: dict) -> dict:
    if not settings.anthropic_api_key:
        raise ContentGenerationError("IA não configurada")

    prompt = _build_prompt(product)
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    last_error = ContentGenerationError("Falha ao gerar conteúdo")
    for _ in range(MAX_ATTEMPTS):
        try:
            return _request_bundle(client, prompt)
        except ContentGenerationError as exc:
            last_error = exc
        except Exception as exc:
            last_error = ContentGenerationError("Falha ao gerar conteúdo")
            last_error.__cause__ = exc
    raise last_error
