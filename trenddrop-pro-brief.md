# TrendDrop PRO — Brief de Produto para Build Real

> Documento de handoff para desenvolvimento do backend real (uso recomendado: Claude Code). Consolida tudo que foi decidido e construído como protótipo no chat.

---

## 1. Visão do produto

**O que é**: um SaaS para lojistas de e-commerce (dropshipping e marketing de afiliados), com dois módulos:

1. **Pesquisa de Produtos** — descoberta e análise de produtos em alta para dropshipping (scores, margens, concorrência, tendências).
2. **Marketing de Afiliados** — gestão de operação de afiliados: catálogo, geração de conteúdo com IA, publicação, auto-limpeza de produtos fracos.

**Modelo de negócio**: SaaS vendido para outras lojas/pessoas se cadastrarem — **não é uso pessoal único**. Isso significa multi-tenant desde o desenho do banco de dados.

**Nome, marca e tagline**: TrendDrop PRO — "Descobrimos o que é tendência. Você aproveita primeiro."

---

## 2. Estado atual: protótipo funcional (anexo)

Existe um protótipo completo em **um único arquivo HTML/CSS/JS**, sem backend, com dados simulados no armazenamento local do navegador. Ele serve como **referência de UI, fluxos e hierarquia de telas** — não é o código a ser reaproveitado linha a linha, mas o comportamento e a estrutura visual devem ser replicados.

**O que já é real no protótipo** (útil reaproveitar a lógica):
- Geração de conteúdo com IA (copy, artigo SEO, roteiro, hooks com score) — chamada real à API da Anthropic (`model: claude-sonnet-4-6`), incluindo o prompt estruturado pedindo JSON.
- Descoberta de produtos via IA com busca na web (tool `web_search_20250305`) no Scan de Tendências, com tentativa de anexar foto real do produto e fallback gracioso quando falha.

**O que é simulado e precisa virar real no backend**:
- Login (aceita qualquer credencial)
- Conexão Meta/TikTok (estrutura de OAuth pronta visualmente, sem autenticar de verdade)
- Conexão com plataformas de afiliados (aceita qualquer link/ID sem validar)
- Todos os dados financeiros, cliques, receita
- Persistência (hoje é local por sessão/navegador, não compartilhada entre dispositivos nem entre usuários)

---

## 3. Identidade de marca

- **Logo**: ícone de chama com gradiente linear (de baixo pra cima: `#00E6A6` → `#00B4FF` → `#7B5CFF`)
- **Paleta**: Primária `#00E6A6` (verde-água), Secundária `#00B4FF` (azul), Destaque `#7B5CFF` (roxo), Fundo Escuro `#0D1117`, Fundo Secundário `#151B23`, Texto `#F3F6F9`
- **Tipografia**: Poppins Bold (títulos) + Inter Regular (texto)
- **Tom visual**: dark mode, cards arredondados, gradiente da marca reservado para CTAs e destaques (não usado em excesso)
- **Redes oficiais**: @trenddroppro (Instagram, TikTok, Facebook)

---

## 4. Estrutura de telas do protótipo (replicar no produto real)

### Módulo "Pesquisa de Produtos" (dropshipping)
| Tela | Conteúdo principal |
|---|---|
| Dashboard | KPIs, top 6 tendências, gráfico de buscas, gráfico de categorias, ranking completo |
| Produtos | Catálogo com filtros (categoria, score mínimo, concorrência) |
| Nichos | 8 nichos com mercado, margem, crescimento |
| Watchlist | Produtos salvos pelo usuário |
| Scan de Tendências | Aciona IA real (busca na web) para descobrir 1 produto novo por scan, com foto quando encontrada |

### Módulo "Marketing de Afiliados"
| Tela | Conteúdo principal |
|---|---|
| Dashboard Financeiro | Receita, produtos em Fase 1/2, publicações automáticas, forecast por plataforma |
| Hub de Afiliações | Status de conexão com Amazon, AliExpress, Shopee, Awin, Rakuten, Kiwify + assistente guiado de conexão |
| Contas Conectadas | Meta e TikTok — status de OAuth, redirect URI, escopos, secrets |
| Catálogo Dinâmico | Produtos ativos + fila de auto-limpeza (nunca remove sem confirmação humana) |
| Geração de Conteúdo | Bundle PT/EN por produto: hooks com ranking, copy, artigo SEO, roteiro — via IA real |
| Revisão de Conteúdo | Fila de bundles gerados, edição, aprovação, bulk review |
| Centro de Comando IA | Master switch de autonomia, regras (sugestões/dia, janela de remoção), resumo da operação |

---

## 5. Requisitos de plataforma multi-tenant (novo, a partir da decisão de vender)

### Papéis de usuário
- **Admin** (dono da plataforma — você): vê todas as lojas cadastradas, gerencia assinaturas/cobrança, acessa métricas globais do negócio (nº de lojas ativas, MRR, churn — não confundir com a receita de afiliados de cada loja), suspende/reativa contas, configura limites por plano, dá suporte (idealmente com capacidade de "entrar" numa conta de cliente para diagnosticar problemas).
- **Lojista/associado** (cliente pagante): só vê e opera os próprios dados. Nunca deve ter acesso a dado de outra loja.

### Isolamento de dados (multi-tenancy)
Toda tabela do banco precisa carregar um `tenant_id` (ou equivalente) e todas as queries devem ser filtradas por ele. Essa é uma decisão de arquitetura de banco, não uma tela — precisa estar certa desde a primeira migration.

### Cobrança e planos — **em aberto, decisões pendentes antes ou durante o build**
- Modelo: grátis + pago? Só pago com trial? Quantos planos, quais limites diferenciam um do outro (ex: nº de scans/dia, nº de bundles de conteúdo/mês, nº de plataformas de afiliados conectáveis)?
- Processador de pagamento recorrente: Stripe é o padrão de mercado para isso.

### Legal — **em aberto**
- Termos de Uso e Política de Privacidade são obrigatórios ao processar dados de terceiros (login, e-mail, dados de operação da loja do cliente). Necessário antes do lançamento público, não é algo que dá pra deixar pra depois.

---

## 6. Arquitetura técnica recomendada

```
Frontend (o app atual, adaptado)
        │
        ▼
Backend (seu servidor)
 ├── API + Autenticação (sessões reais, multi-tenant, admin vs lojista)
 ├── Banco de dados (com isolamento por tenant_id)
 └── Agendador (cron jobs — publicação automática, scans agendados)
        │
        ▼
Integrações externas
 ├── Meta / TikTok (OAuth — requer App Review, ver observações abaixo)
 ├── Plataformas de afiliados (Amazon, AliExpress, Shopee, etc.)
 └── IA (Anthropic Claude — já validado no protótipo, manter)
```

**Sobre OAuth do Meta/TikTok**: exige app registrado no Meta for Developers, conta profissional (Business/Creator) vinculada a uma Página do Facebook para cada lojista, e aprovação via App Review com Advanced Access (porque o app publica em contas que não são suas) — processo de 2 a 4 semanas por permissão, com vídeo demonstrando o fluxo completo. Alternativa para acelerar: uma API intermediária já aprovada pelo Meta (ex. Ayrshare, Postiz), mediante assinatura mensal.

**Stack**: a versão anterior (Emergent) usava FastAPI + MongoDB — pode ser mantida ou revista no início do projeto no Claude Code, dependendo da preferência por dados mais relacionais (Postgres) ou não.

---

## 7. Modelo de dados — entidades principais

- **Tenant / Loja**: dono (usuário), nome da loja, plano ativo, status da assinatura
- **User**: papel (`admin` | `lojista`), tenant_id, credenciais
- **Product** (pesquisa de produtos): nome, emoji/imagem, categoria, score, demanda, concorrência, margem, tendência, preço custo/venda, tags, descrição, volume de busca, saturação, plataformas sugeridas, dicas
- **Niche**: nome, mercado, margem média, crescimento, concorrência, descrição, tags
- **Watchlist**: tenant_id, product_id
- **AffiliatePlatformConnection**: tenant_id, plataforma, status, link/ID de afiliado, métricas (fase, produtos ativos, receita)
- **SocialConnection**: tenant_id, plataforma (meta/tiktok), tokens (criptografados), status
- **CatalogProduct** (afiliados): tenant_id, nome, plataforma, categoria, fase, margem, cliques, receita, momentum, status
- **RemovalQueueItem**: tenant_id, catalog_product_id, motivo, métricas, ação recomendada, status
- **ContentBundle**: tenant_id, product_id, hooks (PT/EN com score), copy/artigo/roteiro (PT/EN), notas, status (pendente/aprovado)
- **CommandSettings**: tenant_id, autonomia on/off, sugestões/dia, janela de remoção, regra estrita
- **Plan**: nome, limites, preço
- **Subscription**: tenant_id, plan_id, status, dados de cobrança (Stripe customer/subscription id)

---

## 8. Roadmap de fases

1. Backend básico + autenticação real (multi-tenant desde o início, papéis admin/lojista)
2. Migração dos dados simulados para o banco (produtos, watchlist, catálogo, configurações)
3. Painel de Admin (lojas cadastradas, assinaturas, métricas globais, suporte)
4. Planos e cobrança recorrente (Stripe)
5. OAuth real do Meta/TikTok (ou API intermediária como atalho)
6. IA de conteúdo e descoberta de produtos com chave própria no servidor (hoje funciona direto do navegador só na demo)
7. Cron jobs de publicação automática
8. Termos de Uso, Política de Privacidade, deploy em domínio próprio

---

## 9. Decisões já tomadas vs. em aberto

**Já decidido**:
- Dois módulos como abas dentro do mesmo app (não painéis separados)
- Construir tudo aos poucos, sem pressa de ter tudo de uma vez
- IA usada para geração de conteúdo e descoberta de produtos: Anthropic Claude
- Vai vender para outras lojas (multi-tenant obrigatório)

**Em aberto** (decidir antes ou durante o build no Claude Code):
- Stack definitiva do backend (manter FastAPI + MongoDB ou migrar)
- Modelo de planos e preços
- Se o suporte a Meta/TikTok será via App Review próprio ou API intermediária paga
- Textos legais (Termos de Uso, Política de Privacidade)

---

## 10. Arquivo de referência

O protótipo funcional (`trenddrop-pro.html`) deve ser usado como fonte de verdade visual e de comportamento ao construir o frontend real — todas as telas, textos, cores e microinterações descritas nele já foram validadas.
