# TrendDrop PRO

SaaS multi-tenant para lojistas de dropshipping e marketing de afiliados. Ver [`trenddrop-pro-brief.md`](trenddrop-pro-brief.md) para o produto completo.

Estado atual: **Fase 1 — backend de autenticação real (multi-tenant), tela de login/cadastro ligada à API.**

## Rodando em dev

### 1. Configurar variáveis de ambiente

```bash
cd backend
cp .env.example .env
```

Preencha no `.env`:

- `MONGODB_URI`: connection string do seu cluster no MongoDB Atlas.
- `JWT_SECRET`: qualquer string aleatória longa (ex: `openssl rand -hex 32`).
- `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET`: criados em [Google Cloud Console](https://console.cloud.google.com/) → APIs & Services → Credentials → OAuth Client ID (tipo "Web application"). Autorize `http://localhost:8000/api/auth/google/callback` como redirect URI.
- `SEED_ADMIN_EMAIL` / `SEED_ADMIN_PASSWORD`: credenciais da sua conta admin da plataforma.

### 2. Instalar dependências e subir o backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m app.seed_admin      # cria/atualiza sua conta admin
uvicorn app.main:app --reload # http://localhost:8000 — docs em /docs
```

### 3. Servir o frontend

Em outro terminal:

```bash
cd frontend
python3 -m http.server 5500
```

Abra `http://localhost:5500/trenddrop-pro.html`.

## Estrutura

```
backend/app/
  main.py           # app FastAPI + CORS
  config.py         # settings (.env)
  db.py             # cliente MongoDB (Motor) + índices
  models.py         # schemas Pydantic
  security.py       # hash de senha, JWT, refresh tokens
  dependencies.py   # get_current_user / require_lojista / require_admin
  auth/router.py    # signup, login, refresh, logout, me
  auth/google.py    # login com Google (OAuth2)
  seed_admin.py      # cria o admin da plataforma
frontend/
  trenddrop-pro.html # protótipo com a tela de auth já ligada à API real
```
