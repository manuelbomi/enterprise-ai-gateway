# Enterprise AI Gateway — An Architect's LiteLLM Blueprint

> A production-ready, multi-provider enterprise AI platform built on LiteLLM.
> Designed as both a **working scaffold** and an **AI Architect's tutorial**.

---

## Table of Contents

1. [What This Is](#1-what-this-is)
2. [Why LiteLLM for Enterprise](#2-why-litellm-for-enterprise)
3. [Architecture Overview](#3-architecture-overview)
4. [The Enterprise Multi-Tenancy Model](#4-the-enterprise-multi-tenancy-model)
5. [How Model Routing Works](#5-how-model-routing-works)
6. [Tech Stack](#6-tech-stack)
7. [Quick Start — Run Locally](#7-quick-start--run-locally)
8. [Project Structure](#8-project-structure)
9. [API Reference](#9-api-reference)
10. [Enterprise Deployment Guide](#10-enterprise-deployment-guide)
    - [10.1 On-Premises vs. Cloud](#101-on-premises-vs-cloud--making-the-right-call)
    - [10.2 Internal vs. External Access](#102-internal-vs-external-access--choosing-your-url-strategy)
    - [10.3 What Changes for Real Deployment](#103-what-changes-in-this-project-for-a-real-deployment)
    - [10.4 Network Architecture Diagram](#104-network-architecture--what-it-looks-like-inside-acme-corp)
    - [10.5 SSL Certificates](#105-ssl-certificates-for-internal-deployment)
    - [10.6 Deployment Options by Size](#106-deployment-options-by-company-size)
    - [10.7 Recommended Deployment Path](#107-recommended-deployment-path-when-joining-a-new-company)
11. [Security Architecture](#11-security-architecture)
12. [Cost Governance](#12-cost-governance)
13. [Extending the Scaffold](#13-extending-the-scaffold)
14. [FastAPI's Role in This Project](#14-fastapis-role-in-this-project)
15. [Admin Cost & Usage Dashboards](#15-admin-cost--usage-dashboards)
16. [LiteLLM vs. Alternatives](#16-litellm-vs-alternatives)

---

## 1. What This Is

Imagine you join a company as the **AI Architect**. The CTO says: *"We want all our teams — HR, Engineering, Logistics, the C-Suite — using AI, but we need governance, cost controls, and no vendor lock-in."*

This project is your answer to that ask.

It is a **fully functional enterprise AI platform** that you can:
- Clone and run locally in 5 minutes
- Customise and deploy to Kubernetes for a real company
- Use as a teaching tool to explain enterprise AI architecture to stakeholders

**What it demonstrates:**
- A unified AI gateway that routes requests to 100+ LLM providers
- Role-Based Access Control (RBAC) with team-based model policies
- Real-time streaming chat with token-by-token output
- Per-team cost tracking and budget enforcement
- A React/TypeScript UI with a chat interface and admin dashboard

---

## 2. Why LiteLLM for Enterprise

Before writing a line of code, an AI Architect must answer: *"Which AI gateway do we use?"*

| Tool | Self-Hosted | Multi-Provider | Team Budgets | Open Source |
|------|-------------|----------------|--------------|-------------|
| **LiteLLM** ✅ | Fully | 100+ providers | Yes | Yes |
| Portkey.ai | Partially (SaaS) | Yes | Yes | No |
| OpenRouter | No | Yes | No | No |
| Azure AI Gateway | Azure-only | Azure only | Partial | No |
| Kong AI Gateway | Yes | With plugins | With plugins | Enterprise tier |

**LiteLLM wins for portable enterprise** because:
1. **100% self-hostable** — your data never leaves your infrastructure
2. **Provider-agnostic** — swap OpenAI for Anthropic or Mistral by changing one config line
3. **Team-aware** — built-in virtual keys, team budgets, and spend tracking
4. **OpenAI-compatible API** — any app that works with OpenAI works with LiteLLM
5. **Active open-source** — 10k+ GitHub stars, production-proven

---

## 3. Architecture Overview

```
┌────────────────────────────────────────────────────────────────────┐
│                     ENTERPRISE AI GATEWAY                           │
│                                                                      │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────────────┐  │
│  │  React UI   │    │  FastAPI    │    │   LiteLLM Proxy         │  │
│  │  (Port 5173)│───▶│  Backend   │───▶│   (Port 4000)           │  │
│  │             │    │  (Port 8000)│    │                         │  │
│  │  Login      │    │             │    │  Routes to:             │  │
│  │  Chat       │    │  Auth/RBAC  │    │  ┌─────────────────┐   │  │
│  │  Dashboard  │    │  Sessions   │    │  │ OpenAI GPT-4o   │   │  │
│  │  Admin      │    │  Analytics  │    │  │ Anthropic Claude│   │  │
│  └─────────────┘    └──────┬──────┘    │  │ Google Gemini   │   │  │
│                            │           │  │ Mistral         │   │  │
│                     ┌──────▼──────┐    │  │ ...100+ more    │   │  │
│                     │ PostgreSQL  │    │  └─────────────────┘   │  │
│                     │ (Users,     │    │                         │  │
│                     │  Sessions,  │    │  Budget enforcement     │  │
│                     │  Usage Logs)│    │  Rate limiting          │  │
│                     └─────────────┘    │  Response caching       │  │
│                     ┌─────────────┐    │  Fallback routing       │  │
│                     │   Redis     │    └─────────────────────────┘  │
│                     │ (Cache,     │                                  │
│                     │  Sessions)  │                                  │
│                     └─────────────┘                                  │
└────────────────────────────────────────────────────────────────────┘
```

**Data flow for a chat message:**

```
User types message
       │
       ▼
React UI (ChatPage.tsx)
  → POST /api/chat/completions/stream
       │
       ▼
FastAPI backend (api/chat.py)
  1. Validate JWT token
  2. Load user's team ModelPolicy from PostgreSQL
  3. Verify requested model is in allowed_models
  4. POST /v1/chat/completions to LiteLLM Proxy
     (using user's virtual key → budget enforced here)
       │
       ▼
LiteLLM Proxy (litellm/config.yaml)
  1. Validate virtual key
  2. Check team budget
  3. Apply rate limit
  4. Translate to provider-native format
  5. Stream response from provider
       │
       ▼
LLM Provider (Anthropic / OpenAI / etc.)
  → Streams tokens back
       │
       ▼
FastAPI → Streams SSE to browser
       │
       ▼
React UI renders tokens in real-time
```

---

## 4. The Enterprise Multi-Tenancy Model

The core governance model maps your org chart to AI access controls:

```
Enterprise
├── C-Suite Team
│   ├── Policy: [claude-opus, gpt-4o] | Budget: $500/mo | RPM: 50
│   └── Users: CEO, CFO, COO
│
├── Engineering Team
│   ├── Policy: [claude-sonnet, gpt-4o, gpt-4o-mini] | Budget: $1000/mo | RPM: 200
│   └── Users: Engineers, Tech Leads
│
├── HR Team
│   ├── Policy: [claude-haiku, gpt-4o-mini] | Budget: $50/mo | RPM: 100
│   └── Users: HR Staff, Recruiters
│
└── Logistics Team
    ├── Policy: [claude-haiku] | Budget: $30/mo | RPM: 100
    └── Users: Ops Staff
```

**How it enforces governance:**
1. **Model restriction** — HR can't accidentally use the expensive Claude Opus
2. **Monthly budget** — Engineering's LLM spend is capped at $1000; LiteLLM returns 429 when hit
3. **Rate limiting** — prevents any single team from overwhelming providers during peak usage
4. **Audit trail** — every call is logged with user, team, model, tokens, cost, and latency

---

## 5. How Model Routing Works

A common question: *"Does LiteLLM automatically pick the right model from the prompt?"*

**No — and that's intentional.** Prompt-based auto-routing is unreliable for enterprise governance. Instead, routing is deterministic:

```
Priority 1: Team assignment (user belongs to HR → HR policy applies)
         ↓
Priority 2: Virtual key restrictions (key only allows claude-haiku, gpt-4o-mini)
         ↓
Priority 3: User's explicit model selection in the UI (must be in allowed list)
         ↓
Priority 4: Team's default_model (fallback when user doesn't pick)
```

**Fallback routing** (what happens when a provider is down):
```yaml
# litellm/config.yaml
fallbacks:
  - gpt-4o: ["claude-sonnet", "gemini-pro"]   # if GPT-4o fails, try Claude Sonnet
  - claude-opus: ["gpt-4o", "claude-sonnet"]   # if Opus is unavailable, try GPT-4o
```

This is LiteLLM's killer feature for enterprise SLAs: **provider outage ≠ service outage**.

---

## 6. Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| **Frontend** | React 18 + TypeScript + Vite | Type safety, fast HMR, industry standard |
| **UI Components** | Tailwind CSS | Utility-first, easy to customise |
| **Charts** | Recharts | React-native, well-maintained |
| **State Management** | Zustand | Lightweight, no Redux boilerplate |
| **Server State** | TanStack Query | Caching, background refetch, loading states |
| **Backend** | FastAPI (Python) | Async, automatic Swagger docs, Pydantic validation |
| **AI Gateway** | LiteLLM Proxy | 100+ providers, budget enforcement, caching |
| **Database** | PostgreSQL 16 | ACID transactions, JSON support, battle-tested |
| **Migrations** | Alembic | Version-controlled schema changes |
| **Cache** | Redis 7 | LiteLLM response caching, session storage |
| **Auth** | JWT (python-jose) | Stateless, horizontally scalable |
| **Passwords** | bcrypt (passlib) | Slow hashing by design, brute-force resistant |
| **Containerisation** | Docker + Compose | Reproducible local dev environment |
| **Orchestration** | Kubernetes | Production scaling and HA |
| **Reverse Proxy** | nginx | TLS termination, static file serving |

---

## 7. Quick Start — Run Locally

### Prerequisites

- Docker Desktop (Windows/Mac) or Docker Engine + Compose (Linux)
- Node.js 20+ (for frontend dev outside Docker)
- Python 3.11+ (for backend dev outside Docker)
- At least one LLM API key (OpenAI, Anthropic, etc.)

### Steps

**1. Clone and configure**
```bash
git clone https://github.com/YOUR_USERNAME/enterprise-ai-gateway.git
cd enterprise-ai-gateway

# Copy the env template
cp .env.example .env

# Edit .env — add your API keys at minimum:
# OPENAI_API_KEY=sk-...
# ANTHROPIC_API_KEY=sk-ant-...
```

**2. Start all services**
```bash
docker compose up --build
```

Wait ~60 seconds for all services to start. You'll see:
```
ai_gateway_postgres  | database system is ready to accept connections
ai_gateway_redis     | Ready to accept connections
ai_gateway_litellm   | LiteLLM Proxy: Uvicorn running on 0.0.0.0:4000
ai_gateway_backend   | Uvicorn running on http://0.0.0.0:8000
ai_gateway_frontend  | Local: http://localhost:5173/
```

**3. Run database migrations**
```bash
docker compose exec backend alembic upgrade head
```

**4. Create the first super admin user**
```bash
docker compose exec backend python -c "
from app.database import *
from app.models.user import User, UserRole
from app.services.auth_service import hash_password
import asyncio

async def create_admin():
    async with AsyncSessionLocal() as db:
        admin = User(
            email='admin@company.com',
            full_name='System Admin',
            hashed_password=hash_password('Admin123!'),
            role=UserRole.SUPER_ADMIN,
        )
        db.add(admin)
        await db.commit()
        print('Admin created: admin@company.com / Admin123!')

asyncio.run(create_admin())
"
```

**5. Open the app**
- **Frontend UI**: http://localhost:5173 — login with `admin@company.com` / `Admin123!`
- **API Docs (Swagger)**: http://localhost:8000/docs
- **LiteLLM Admin UI**: http://localhost:4000/ui

---

## 8. Project Structure

```
enterprise-ai-gateway/
│
├── backend/                    # FastAPI Python backend
│   ├── main.py                 # App entry point, router registration
│   ├── requirements.txt
│   ├── Dockerfile
│   └── app/
│       ├── config.py           # Pydantic Settings — all config from env vars
│       ├── database.py         # Async SQLAlchemy engine + session factory
│       ├── models/
│       │   ├── user.py         # User + UserRole ORM models
│       │   ├── team.py         # Team + ModelPolicy ORM models
│       │   └── usage.py        # ChatSession + Message + UsageLog ORM models
│       ├── schemas/
│       │   ├── auth.py         # Login/register request+response schemas
│       │   └── chat.py         # Chat request+response schemas
│       ├── api/
│       │   ├── auth.py         # POST /auth/login, /auth/register, GET /auth/me
│       │   ├── chat.py         # POST /chat/completions (stream+standard)
│       │   └── admin.py        # Admin: teams, users, analytics
│       ├── services/
│       │   ├── auth_service.py      # JWT, bcrypt, user lookup
│       │   └── litellm_service.py   # LiteLLM proxy client, virtual key management
│       └── middleware/
│           └── auth.py         # JWT dependency injection, role guards
│
├── frontend/                   # React/TypeScript frontend
│   ├── src/
│   │   ├── App.tsx             # Router, auth guards, QueryClient
│   │   ├── main.tsx            # React entry point
│   │   ├── index.css           # Tailwind + global styles
│   │   ├── types/index.ts      # Shared TypeScript interfaces
│   │   ├── services/api.ts     # Axios client, all API calls
│   │   ├── store/
│   │   │   ├── authStore.ts    # Zustand: user auth state
│   │   │   └── chatStore.ts    # Zustand: chat sessions + streaming
│   │   ├── pages/
│   │   │   ├── Login/LoginPage.tsx
│   │   │   ├── Chat/ChatPage.tsx       # Main chat interface
│   │   │   ├── Dashboard/DashboardPage.tsx  # Analytics
│   │   │   └── Admin/AdminPage.tsx     # Team + user management
│   │   └── components/
│   │       └── Layout/MainLayout.tsx   # Sidebar + app shell
│   ├── package.json
│   ├── vite.config.ts
│   └── Dockerfile              # Multi-stage: dev, builder, production
│
├── litellm/
│   └── config.yaml             # LiteLLM model definitions, routing, caching
│
├── k8s/                        # Kubernetes manifests
│   ├── namespace.yaml
│   ├── backend/deployment.yaml
│   ├── litellm/deployment.yaml
│   └── ingress.yaml            # nginx Ingress with TLS (cert-manager)
│
├── .env.example                # Environment variable template
├── docker-compose.yml          # Local development stack
└── README.md                   # This file
```

---

## 9. API Reference

The FastAPI backend auto-generates Swagger docs at `/docs` (dev mode).

**Key endpoints:**

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/auth/login` | Public | Email + password → JWT tokens |
| GET | `/auth/me` | Bearer | Returns current user profile |
| POST | `/auth/register` | Super Admin | Create a new user |
| POST | `/chat/completions` | Bearer | Standard (non-streaming) chat |
| POST | `/chat/completions/stream` | Bearer | SSE streaming chat |
| GET | `/chat/sessions` | Bearer | List user's chat sessions |
| GET | `/chat/sessions/{id}` | Bearer | Load session with messages |
| POST | `/admin/teams` | Super Admin | Create a team + model policy |
| GET | `/admin/teams` | Admin | List all teams |
| POST | `/admin/teams/{id}/assign-user` | Super Admin | Assign user to team |
| GET | `/admin/analytics/usage-by-team` | Admin | Cost per team (last N days) |
| GET | `/admin/analytics/daily-cost` | Super Admin | Daily spend trend |
| GET | `/health` | Public | Health check for load balancers |

---

## 10. Enterprise Deployment Guide

This section answers the most common question an AI Architect faces: *"Where do we actually run this thing?"*

---

### 10.1 On-Premises vs. Cloud — Making the Right Call

**Short answer: Private Cloud (VPC) is the enterprise sweet spot.** Pure on-premises is increasingly rare except in highly regulated industries. Here is why:

| Consideration | Pure On-Prem | Private Cloud (VPC) | Public Cloud |
|---|---|---|---|
| Data sovereignty | ✅ Best | ✅ Good (private VPC) | ⚠️ Depends on config |
| LLM API calls | Still leave premises | Still leave premises | Still leave premises |
| Infra maintenance | ❌ Your team owns it | ✅ Cloud manages hardware | ✅ Cloud manages hardware |
| Cost at scale | ✅ Cheaper long-term | Middle ground | ❌ Can escalate quickly |
| Regulated industries (HIPAA, SOX, FedRAMP) | ✅ Easiest to certify | ✅ Works with right config | ⚠️ Needs compliance tier |
| Time to first deploy | ❌ Weeks / months | ✅ Days | ✅ Hours |
| Scaling capacity | ❌ Physical hardware buys | ✅ Autoscaling | ✅ Autoscaling |

> **Important caveat on data sovereignty**: Regardless of where you host the *platform*, LLM API calls (OpenAI, Anthropic, Google, etc.) always leave your network and are processed by the provider. If your company's data policy prohibits sending prompts to third-party APIs, you must add locally-hosted models via **Ollama** (which LiteLLM supports natively — just add `model: ollama/llama3` to `litellm/config.yaml`). This is a conversation to have with your CISO on day one.

---

### 10.2 Internal vs. External Access — Choosing Your URL Strategy

When you deploy this platform inside a company, `localhost:5173` is replaced with a real, meaningful hostname. There are two approaches:

#### Option A — Internal Only (Intranet / VPN) — Recommended Starting Point

The application lives inside the corporate network. Employees access it on the company network or through VPN from home:

```
Example URL:   https://ai.acme.internal      (pure intranet DNS)
           or  https://aigateway.acme.com    (company domain, internal DNS only)
```

**How it works**: The IT/Network admin creates one DNS A record:
```
ai.acme.internal  →  10.0.1.50   (the server's private IP address)
```
Every employee's laptop already uses the company's internal DNS resolver, so the URL works for the entire company automatically — no changes needed on individual machines.

**Why CISOs prefer this**: Nothing is publicly reachable. An attacker on the internet cannot even find the login page. Access requires being inside the corporate network or authenticated to VPN.

#### Option B — Internet-Facing (Accessible Anywhere)

```
Example URL:   https://ai.acme.com
           or  https://aigateway.acme.com
```

**Use when**: The company has remote workers without a corporate VPN, or the platform needs to be accessible from mobile devices on personal networks.

**Additional requirements**:
- A Web Application Firewall (WAF) in front of nginx (AWS WAF, Cloudflare, Azure Front Door)
- Proper public SSL certificate (Let's Encrypt via cert-manager, or a commercial CA)
- IP allowlisting if you want to restrict to known office/VPN IP ranges

---

### 10.3 What Changes in This Project for a Real Deployment

Only three places reference the hostname. Update them all before deploying:

**1. `.env` — CORS must match your real domain**

```bash
# Development (default):
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5173

# Internal deployment:
ALLOWED_ORIGINS=https://ai.acme.internal

# External deployment:
ALLOWED_ORIGINS=https://ai.acme.com
```

**2. `k8s/ingress.yaml` — set the real hostname**

```yaml
# Replace:
  - host: yourdomain.com

# With (internal):
  - host: ai.acme.internal

# Or (external):
  - host: ai.acme.com
```

Also update the TLS secret name section:
```yaml
  tls:
    - hosts:
        - ai.acme.com
      secretName: ai-gateway-tls
```

**3. Frontend production build — set the API base URL**

Create `frontend/.env.production` (see `frontend/.env.production.example`):
```bash
VITE_API_URL=https://ai.acme.com/api
```

This file is consumed by Vite at build time and baked into the static JS bundle — there is no runtime config file in a React SPA.

---

### 10.4 Network Architecture — What It Looks Like Inside ACME Corp

```
ACME Corporate Network
│
├── Office Employees (Windows/Mac laptops on company Wi-Fi)
│    └── Browser → https://ai.acme.internal ─────────────────────────┐
│                                                                      │
├── Remote Employees (working from home)                              │
│    └── Cisco/Palo Alto VPN → https://ai.acme.internal ─────────────▼
│                                                               ┌──────────────┐
│                                                               │    nginx      │
│                                                               │  Reverse     │
│                                                               │  Proxy       │
│                                                               │  Port 443    │
│                                                               │  (TLS term.) │
│                                                               └──────┬───────┘
│                                                                      │
│                                                        ┌─────────────┴───────────────┐
│                                                        │                             │
│                                                   ┌────▼─────┐              ┌────────▼────┐
│                                                   │ Frontend  │              │  Backend    │
│                                                   │ (nginx    │              │  FastAPI    │
│                                                   │  static)  │              │  Port 8000  │
│                                                   └──────────┘              └────────┬────┘
│                                                                                       │
│                                                                              ┌────────▼────┐
│                                                                              │  LiteLLM    │
│                                                                              │  Proxy      │
│                                                                              │  Port 4000  │
│                                                                              │  (internal  │
│                                                                              │   only)     │
│                                                                              └────────┬────┘
│                                                                                       │
│                                                              ┌────────────────────────▼──────────┐
└──────────────────────────── Internet ────────────────────────▶  OpenAI / Anthropic / Google /    │
                                                               │  Mistral  (LLM API calls)         │
                                                               └───────────────────────────────────┘
```

> **Note**: LiteLLM is never exposed externally. Its port 4000 is only reachable by the FastAPI backend within the private network. All LLM API calls originate from the LiteLLM container — provider API keys never touch employee browsers.

---

### 10.5 SSL Certificates for Internal Deployment

| Approach | How | Best For |
|---|---|---|
| **Internal CA** | IT issues certs from your company's Certificate Authority | Enterprises with existing PKI infrastructure |
| **Split-horizon DNS** | `ai.acme.com` resolves to private IP inside network, public IP outside | Companies that want one domain for inside + outside |
| **Let's Encrypt (cert-manager)** | Auto-issued free public certificate | External deployments only (needs public domain) |
| **Self-signed cert** | Generated on the server | Dev/POC only — browsers warn, IT can push trust via Group Policy/MDM |

For the Kubernetes deployment, cert-manager handles this automatically once you configure a ClusterIssuer (see `k8s/ingress.yaml` annotations).

---

### 10.6 Deployment Options by Company Size

#### Option A: Docker Compose on a Single VM (Small Teams / POC)

Good for: internal tools, proof-of-concept, teams under 50 users, or when you need to prove value before getting budget for Kubernetes.

```bash
# On your server (SSH in first):
git clone https://github.com/YOUR_USERNAME/enterprise-ai-gateway.git
cd enterprise-ai-gateway
cp .env.example .env
# Edit .env with real values
nano .env

# Start everything
docker compose up -d --build

# Run migrations once
docker compose exec backend alembic upgrade head

# Check status
docker compose ps
docker compose logs -f backend
```

The server's IP (or DNS name `ai.acme.internal`) is now your access URL. Tell IT to point the DNS record here.

**Update process** (zero-downtime if you have a load balancer upstream):
```bash
git pull
docker compose up -d --build
docker compose exec backend alembic upgrade head
```

#### Option B: Kubernetes (Production / Enterprise Scale)

Good for: multi-team enterprise, 100+ users, high availability requirements, teams that already have a Kubernetes cluster.

**Prerequisites:**
- Kubernetes cluster (EKS on AWS, GKE on GCP, AKS on Azure, or on-prem k8s)
- `kubectl` configured and pointing at the cluster
- nginx Ingress Controller installed
- cert-manager installed (for TLS)
- Container registry (ECR, GCR, ACR, or Docker Hub)

```bash
# 1. Build and push images to your registry
docker build -t your-registry/ai-gateway-backend:v1.0.0 ./backend
docker build -t your-registry/ai-gateway-frontend:v1.0.0 ./frontend
docker push your-registry/ai-gateway-backend:v1.0.0
docker push your-registry/ai-gateway-frontend:v1.0.0

# 2. Create namespace
kubectl apply -f k8s/namespace.yaml

# 3. Store secrets (never put real values in YAML files)
kubectl create secret generic ai-gateway-secrets \
  --from-env-file=.env \
  --namespace enterprise-ai

# 4. Mount LiteLLM config as a ConfigMap
kubectl create configmap litellm-config \
  --from-file=config.yaml=./litellm/config.yaml \
  --namespace enterprise-ai

# 5. Deploy all services
kubectl apply -f k8s/

# 6. Run database migrations
kubectl exec -n enterprise-ai deployment/ai-gateway-backend -- \
  alembic upgrade head

# 7. Verify rollout
kubectl rollout status deployment/ai-gateway-backend -n enterprise-ai
kubectl get pods -n enterprise-ai

# 8. Check the Ingress got an external IP
kubectl get ingress -n enterprise-ai
```

#### Option C: Cloud-Managed Services (Reduce Infrastructure Ops)

For enterprises on a single cloud provider, swap containers for managed services:

| Component | AWS | Azure | GCP |
|---|---|---|---|
| Backend | ECS Fargate / App Runner | Azure Container Apps | Cloud Run |
| Database | RDS PostgreSQL | Azure Database for PostgreSQL | Cloud SQL |
| Cache | ElastiCache Redis | Azure Cache for Redis | Memorystore |
| Container Registry | ECR | ACR | Artifact Registry |
| Load Balancer | ALB | Azure Application Gateway | Cloud Load Balancing |
| TLS / Cert | ACM (free) | Azure Key Vault | Certificate Manager |
| Secrets | AWS Secrets Manager | Azure Key Vault | Secret Manager |

> LiteLLM still runs as a container even in cloud deployments — there is no managed equivalent. It *is* the managed service layer for your LLMs.

---

### 10.7 Recommended Deployment Path When Joining a New Company

This is the realistic week-by-week roadmap an AI Architect would follow:

```
Week 1–2:  Single VM with Docker Compose
           ─────────────────────────────
           → Spin up on one server (cloud VM or on-prem box)
           → Ask IT for internal DNS: ai.acme.internal → server IP
           → Share URL with 5–10 pilot users (your immediate team)
           → Prove it works, gather feedback, show cost tracking to finance

Month 1–2: Move to Kubernetes (cloud private VPC)
           ──────────────────────────────────────
           → Deploy to EKS/AKS/GKE in a private subnet
           → Set up proper internal DNS and SSL certificate
           → Roll out to all departments, one team at a time
           → Set per-team budgets in LiteLLM based on pilot data

Month 2–3: SSO Integration
           ─────────────────
           → Replace email+password login with company SSO
             (Okta, Azure AD, Google Workspace, Ping Identity)
           → Employees log in with their existing company credentials
           → No separate password management, automatic deprovisioning
             when someone leaves the company

Month 3+:  Governance hardening
           ──────────────────────
           → Add local/self-hosted models (Ollama) for sensitive prompts
           → Plug in Langfuse or Langsmith for full prompt observability
           → Export UsageLog to company BI tool (Tableau, Power BI, Metabase)
           → Present monthly AI spend dashboard to leadership
```

---

## 11. Security Architecture

### Authentication
- **JWT (stateless)**: tokens expire in 60 minutes; refresh tokens last 7 days
- **bcrypt passwords**: work factor = 12 (adjustable) — intentionally slow to defeat brute-force
- **No session DB**: scale horizontally without sticky sessions

### Secrets Management
- **Never commit `.env`** — it's in `.gitignore`
- **Local dev**: `.env` file
- **Kubernetes**: `kubectl create secret` — stored in etcd (encrypt at rest)
- **Cloud**: use provider secret managers (AWS Secrets Manager, Azure Key Vault, GCP Secret Manager)

### Network Security
- All inter-service communication is on the private Docker/Kubernetes network
- LiteLLM Proxy is **not** exposed externally — only the backend can reach it
- nginx terminates TLS; internal services speak plain HTTP

### API Security
- CORS restricted to your frontend domain (`ALLOWED_ORIGINS` env var)
- Rate limiting at the LiteLLM proxy layer (RPM/TPM per virtual key)
- Role-based endpoint guards (`require_super_admin`, `require_team_admin`)
- Input validation via Pydantic (all API inputs are schema-validated)

---

## 12. Cost Governance

LiteLLM tracks spend per virtual key (= per user) and aggregates it per team.

**Budget enforcement flow:**
```
User sends message
→ FastAPI forwards to LiteLLM Proxy with user's virtual key
→ LiteLLM checks team's current spend against max_budget
→ If over budget → returns 429 "Budget exceeded"
→ FastAPI surfaces error to UI: "Your team's monthly budget has been reached"
```

**Monitoring:**
- **LiteLLM UI** (`http://localhost:4000/ui`): real-time spend dashboard built into LiteLLM
- **Admin Dashboard** (`/dashboard`): team cost breakdown and daily trend charts built into this app
- **UsageLog table**: queryable by any BI tool (Metabase, Redash, Grafana)

---

## 13. Extending the Scaffold

Common enterprise customisations:

**SSO/LDAP Integration**
Replace the email/password login with SAML 2.0 or OIDC:
- Add `python-saml` or `authlib` to `requirements.txt`
- Replace `POST /auth/login` with an OIDC redirect flow
- Keep the JWT layer — OIDC gives you the user identity, JWT is still used internally

**Document Upload (RAG)**
To let users ask questions about company documents:
1. Add `langchain` + `pgvector` PostgreSQL extension
2. Create a `/documents/upload` endpoint that chunks and embeds documents
3. In `api/chat.py`, retrieve relevant chunks before forwarding to LiteLLM

**Audit Logging**
The `UsageLog` table is your audit trail. To enhance it:
- Log the full prompt + response (consider data privacy regulations first)
- Add a `PII_detected` flag using a classifier model
- Export logs to a SIEM (Splunk, Datadog) via a background worker

**Multi-Language UI**
Add `react-i18next` to the frontend for internationalisation.

---

## 14. FastAPI's Role in This Project

**One-line summary**: FastAPI is the business logic and security layer that sits between the React UI and LiteLLM. The UI never talks to LiteLLM directly — everything goes through FastAPI first.

```
React UI  →  FastAPI :8000  →  LiteLLM Proxy :4000  →  OpenAI / Anthropic / etc.
```

### Duty 1 — Authentication & Authorization (`app/api/auth.py`, `app/middleware/auth.py`)

FastAPI owns the entire identity system:

- Issues JWT tokens when a user logs in (`POST /auth/login`)
- Validates JWT tokens on every protected request via the `Depends(get_current_user)` dependency
- Enforces roles — only `super_admin` can create users; only `team_admin` can see analytics
- Hashes and verifies passwords using bcrypt

LiteLLM has no concept of your users. It knows virtual keys, not people. FastAPI bridges that gap.

```
Browser sends:  Authorization: Bearer eyJhbGci...   (the user's JWT)
FastAPI checks: Is this token valid? Who is this user? What role? What team?
LiteLLM sees:   Bearer sk-litellm-abc123             (a virtual key — not the user's JWT)
```

### Duty 2 — Model Routing Policy Enforcement (`app/api/chat.py`)

This is FastAPI's most important enterprise duty. Before any message reaches LiteLLM, FastAPI:

1. Loads the user's **Team** and **ModelPolicy** from PostgreSQL
2. Checks whether the requested model is in `policy.allowed_models`
3. If no model specified, selects the team's `default_model`
4. Retrieves the user's LiteLLM virtual key
5. Rejects the request with `403 Forbidden` if the model is not permitted

LiteLLM alone cannot do this — it has no knowledge that HR is only allowed `claude-haiku`. FastAPI is where that business rule lives.

```python
# From app/api/chat.py — this logic does not exist in LiteLLM
if requested_model not in policy.allowed_models:
    raise HTTPException(403, "Model not available for your team")
```

### Duty 3 — Single Controlled Entry Point for the UI (`app/api/chat.py`)

The React frontend has **one API to call**: FastAPI on port 8000. LiteLLM's port 4000 is never exposed publicly. FastAPI acts as a controlled gateway, which means:

- Request inspection (PII detection, content filtering) can be added in one place
- Specific users can be throttled or blocked without touching LiteLLM config
- LiteLLM's admin port stays completely internal to the server network

### Duty 4 — Database Read/Write (`app/database.py`, all models)

LiteLLM has its own internal Postgres tables for keys and spend. FastAPI owns the **application database** — the data that matters to the business:

| Table | FastAPI's duty |
|---|---|
| `users` | Create, authenticate, deactivate users |
| `teams` | Create teams, assign users, sync with LiteLLM |
| `model_policies` | Store and enforce per-team model access rules |
| `chat_sessions` | Group messages into conversation threads |
| `messages` | Persist every user message and AI reply |
| `usage_logs` | Record tokens, cost, latency per call for the analytics dashboard |

None of this lives in LiteLLM. It is all FastAPI + PostgreSQL.

### Duty 5 — Usage Logging & Analytics (`app/api/chat.py`, `app/api/admin.py`)

After every LLM call, FastAPI writes a `UsageLog` row capturing: user, team, model, prompt tokens, completion tokens, cost in USD, latency in milliseconds, and success/failure. The admin analytics endpoints query this table to power dashboard charts. LiteLLM's own spend logs are separate and less rich (they don't carry session context or user identity beyond the key).

### Duty 6 — SSE Streaming Proxy (`app/api/chat.py`)

When streaming is enabled, FastAPI opens a streaming connection to LiteLLM and immediately pipes each token chunk to the browser via `StreamingResponse`. It does not buffer — this is what creates the real-time "typing" effect in the UI.

```
LiteLLM emits token → FastAPI receives it → Browser gets it → React appends to screen
                       (zero buffering — no waiting for the full response)
```

### Duty 7 — Admin Operations (`app/api/admin.py`)

FastAPI exposes the AI Architect's onboarding workflows:

- `POST /admin/teams` — creates a team in the app DB **and** registers it in LiteLLM via its management API
- `POST /admin/teams/{id}/assign-user` — assigns a user to a team **and** generates their LiteLLM virtual key
- `GET /admin/analytics/*` — queries the `usage_logs` table for cost dashboards

### Duty 8 — Input Validation (`app/schemas/`)

All incoming data is validated by Pydantic schemas before FastAPI touches it: email format, password length, valid message roles, model names against the allowed list. LiteLLM and the database never see malformed input.

### Duty 9 — Auto-Generated API Documentation

FastAPI automatically produces interactive Swagger docs at `http://localhost:8000/docs` (dev mode). Every endpoint, request schema, and response schema is documented with zero extra effort. This is what you demo to the CTO on day one.

### The Clean Separation of Concerns

```
┌──────────────────────────────────────────────────────────┐
│  React UI                                                 │
│  "Show me a chat interface and handle user sessions"      │
└───────────────────────────┬──────────────────────────────┘
                            │  HTTPS  (JWT Bearer token)
┌───────────────────────────▼──────────────────────────────┐
│  FastAPI                                                  │
│  "Enforce security, apply business rules,                 │
│   log everything, talk to the database,                   │
│   then forward the LLM request"                           │
└───────────────────────────┬──────────────────────────────┘
                            │  HTTP  (LiteLLM virtual key)
┌───────────────────────────▼──────────────────────────────┐
│  LiteLLM Proxy                                            │
│  "I only know models, keys, budgets, and rate limits.     │
│   Translate the request and call the right provider."     │
└───────────────────────────┬──────────────────────────────┘
                            │  HTTPS  (provider API key)
┌───────────────────────────▼──────────────────────────────┐
│  OpenAI / Anthropic / Google / Mistral                    │
└──────────────────────────────────────────────────────────┘
```

Each layer does exactly one job. FastAPI's job is everything that requires knowing *who the user is* and *what they are allowed to do* — which turns out to be most of the application.

---

## 15. Admin Cost & Usage Dashboards

Enterprises need answers to these questions every week:

- *"How much did the Engineering team spend on AI this month?"*
- *"Which user is consuming the most tokens?"*
- *"Is Logistics close to their monthly budget?"*
- *"Which model costs us the most — GPT-4o or Claude Opus?"*

This platform provides **three ways** to get those answers, ordered by increasing sophistication.

### Level 1 — Built-in Dashboard (ships with this project)

The `/dashboard` page in this application renders live charts from the `usage_logs` table:

| Chart | Data source | Endpoint |
|---|---|---|
| Cost by department (bar chart) | `usage_logs` grouped by `team_id` | `GET /admin/analytics/usage-by-team` |
| Daily spend trend (line chart) | `usage_logs` grouped by date | `GET /admin/analytics/daily-cost` |
| Team breakdown table | Same as above | Same as above |

**Who can access it**: Any user with `team_admin` or `super_admin` role.
**How to open it**: Log in → click **Dashboard** in the left sidebar.

The built-in dashboard is intentionally simple — it proves the data is there. For richer analytics, use Levels 2 or 3 below.

### Level 2 — Enterprise AI Monitor (companion project)

For weekly and per-user breakdowns, budget alerts, and model cost comparisons, this repository has a companion project:

> **[enterprise-ai-monitor](../enterprise-ai-monitor/)** — a dedicated React analytics dashboard that connects to this platform's API and surfaces all the cost governance data an AI Architect needs to present to leadership.

It adds the following views that are not in this project's built-in dashboard:

| View | What it shows |
|---|---|
| **Overview** | Total spend, calls, tokens — today / this week / this month |
| **Cost by Team** | Bar chart + table with budget-remaining indicator per department |
| **Cost by User** | Ranked table of top spenders — catches runaway usage early |
| **Cost by Model** | Which provider/model costs the most and is used the most |
| **Budget Status** | Traffic-light indicators (green / amber / red) per team vs. their monthly limit |
| **Weekly Report** | Printable summary with trends — designed to email to the CTO |

See the companion project's README for setup instructions. It is a pure frontend — it reads from this project's existing backend API and requires no additional infrastructure.

### Level 3 — Connect a BI Tool (Metabase / Grafana / Power BI)

For the most flexible reporting, point a BI tool directly at the PostgreSQL `usage_logs` table. This requires no code changes — just a read-only database connection.

**Useful queries for a BI dashboard:**

```sql
-- Weekly cost per department (last 8 weeks)
SELECT
    t.name                              AS department,
    DATE_TRUNC('week', ul.created_at)   AS week,
    SUM(ul.cost_usd)                    AS total_cost_usd,
    SUM(ul.total_tokens)                AS total_tokens,
    COUNT(ul.id)                        AS total_calls
FROM usage_logs ul
JOIN teams t ON t.id = ul.team_id
WHERE ul.created_at >= NOW() - INTERVAL '8 weeks'
  AND ul.success = TRUE
GROUP BY t.name, week
ORDER BY week DESC, total_cost_usd DESC;

-- Top 10 users by spend this month
SELECT
    u.full_name,
    u.email,
    t.name                              AS team,
    SUM(ul.cost_usd)                    AS spend_usd,
    SUM(ul.total_tokens)                AS tokens_used,
    COUNT(ul.id)                        AS api_calls
FROM usage_logs ul
JOIN users  u ON u.id = ul.user_id
JOIN teams  t ON t.id = ul.team_id
WHERE ul.created_at >= DATE_TRUNC('month', NOW())
GROUP BY u.full_name, u.email, t.name
ORDER BY spend_usd DESC
LIMIT 10;

-- Cost breakdown by model this month
SELECT
    model_alias,
    model_actual,
    COUNT(*)                            AS call_count,
    SUM(total_tokens)                   AS total_tokens,
    SUM(cost_usd)                       AS total_cost_usd,
    ROUND(AVG(latency_ms))              AS avg_latency_ms
FROM usage_logs
WHERE created_at >= DATE_TRUNC('month', NOW())
  AND success = TRUE
GROUP BY model_alias, model_actual
ORDER BY total_cost_usd DESC;

-- Budget utilisation per team (% of monthly limit used)
SELECT
    t.name                              AS team,
    mp.spend_limit_usd                  AS monthly_budget_usd,
    COALESCE(SUM(ul.cost_usd), 0)       AS spent_this_month_usd,
    ROUND(
        COALESCE(SUM(ul.cost_usd), 0)
        / NULLIF(mp.spend_limit_usd, 0) * 100, 1
    )                                   AS pct_used
FROM teams t
JOIN model_policies mp ON mp.team_id = t.id
LEFT JOIN usage_logs ul
       ON ul.team_id = t.id
      AND ul.created_at >= DATE_TRUNC('month', NOW())
GROUP BY t.name, mp.spend_limit_usd
ORDER BY pct_used DESC NULLS LAST;
```

**Recommended BI tools by company type:**

| Tool | Best for | Setup effort |
|---|---|---|
| **Metabase** (open-source) | Small/mid-size teams, self-hosted, no-code charts | Low |
| **Grafana** | Engineering/DevOps teams already using it for infra monitoring | Medium |
| **Power BI** | Companies already on Microsoft 365 | Low (native Postgres connector) |
| **Tableau** | Large enterprises with a dedicated analytics team | High |
| **Redash** | Developers who want SQL-first dashboards | Low |

For Metabase: install it via Docker (`docker run -p 3001:3000 metabase/metabase`), connect it to the same PostgreSQL instance, and build your first dashboard in under an hour with no SQL required.

---

## 16. LiteLLM vs. Alternatives

| Feature | LiteLLM | Portkey | LangChain | Build Your Own |
|---------|---------|---------|-----------|----------------|
| Self-hosted | ✅ | Partial | ✅ | ✅ |
| Multi-provider | ✅ 100+ | ✅ 200+ | ✅ | ✅ |
| Virtual keys + teams | ✅ | ✅ | ❌ (not built-in) | Custom |
| Budget enforcement | ✅ | ✅ | ❌ | Custom |
| Response caching | ✅ Redis | ✅ Semantic | ❌ | Custom |
| OpenAI-compatible API | ✅ | ✅ | ❌ | Custom |
| Fallback routing | ✅ | ✅ | ✅ (chains) | Custom |
| Agent/chains framework | ❌ (not its job) | ❌ | ✅ | Custom |
| Open source | ✅ MIT | ❌ | ✅ MIT | N/A |

**Decision guide:**
- Need a **pure AI gateway** (routing, budgets, keys)? → **LiteLLM**
- Need **agent orchestration** (chains, memory, tools)? → **LangChain** (use alongside LiteLLM)
- Willing to pay for **managed observability + guardrails**? → **Portkey**
- Already on **Azure/AWS** and want less infra to manage? → **Azure AI Gateway / Bedrock**

---

*Built as an enterprise AI architecture reference. Download, fork, and deploy.*
