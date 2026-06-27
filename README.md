# 🏙️ KSA Real Estate Investment Agent

> An enterprise-grade, multi-agent AI pipeline that ingests unstructured
> real estate listing data from the Riyadh, Saudi Arabia market,
> normalizes it against a strict investment schema, runs quantitative
> analysis to surface undervalued assets, flags regulatory compliance
> risks under Saudi RERA law, and delivers structured investment-grade
> due diligence reports — autonomously.

Built as a cornerstone portfolio project targeting **senior AI Engineering
roles in the GCC region**. Every architectural decision reflects
production engineering standards: strict typing, structured logging,
custom exception hierarchies, deterministic quantitative tooling,
and a fully containerized async deployment pipeline.

---

## 📋 Table of Contents

- [Problem Statement](#-problem-statement)
- [Solution Overview](#-solution-overview)
- [System Architecture](#-system-architecture)
- [Agent Topology](#-agent-topology)
- [Tech Stack](#-tech-stack)
- [Project Structure](#-project-structure)
- [Build Status](#-build-status)
- [Quick Start](#-quick-start)
- [API Reference](#-api-reference)
- [Evaluation Suite](#-evaluation-suite)
- [Deployment](#-deployment)
- [Engineering Decisions](#-engineering-decisions)
- [Roadmap](#-roadmap)

---

## 🎯 Problem Statement

Riyadh's real estate market is **informationally inefficient**:

- Listing data is fragmented across multiple Arabic and English platforms
- Prices for comparable properties vary wildly with no benchmark reference
- Regulatory risks (RERA compliance, Waqf properties, foreign ownership
  restrictions) are buried in unstructured listing text
- No retail investor has the analytical infrastructure to identify
  genuinely undervalued assets before institutional buyers do

**What currently happens without this system:**

| Step | Manual Process | Time Cost |
|------|---------------|-----------|
| Data collection | Visit 3-4 websites separately | 2-3 hours |
| Price comparison | Manual SAR/sqft vs SAR/m² conversion | 1 hour |
| Benchmarking | No district-level reference available | N/A |
| Compliance check | Read individual listing fine print | 2-4 hours |
| Decision | Gut feel + agent recommendation | Unreliable |

**Total: 6-8 hours of manual work per analysis cycle, with high error rate.**

---

## 💡 Solution Overview

An autonomous 4-agent AI pipeline that transforms fragmented,
bilingual, unstructured Riyadh real estate data into investment-grade
due diligence reports in minutes.

NPUT:  "Analyze the villa and apartment market in Olaya and KAFD"

│

▼

┌───────────────────────────────────────────────────────┐

│            KSA Real Estate Investment Agent            │

│                                                       │

│  Sourcing → Cleaning → Analysis → Risk → Report      │

└───────────────────────────────────────────────────────┘

│

▼

OUTPUT: Structured investment report with:

✅ District price benchmarks (SAR/m²)

✅ Ranked undervalued listings (>20% below district avg)

✅ RERA compliance flags

✅ Waqf property warnings

✅ Foreign ownership restriction alerts

✅ Statistical outlier detection (fraud indicators)


**Business Value:** 6-8 hours of manual analyst work → under 5 minutes.

---

## 🏛️ System Architecture

### High-Level Architecture

┌─────────────────────────────────────────────────────────────┐

│                    CLIENT LAYER                              │

│         Streamlit Dashboard  │  REST API Consumers          │

└──────────────────┬───────────────────────┬──────────────────┘

│ HTTP                  │ HTTP

┌──────────────────▼───────────────────────▼──────────────────┐

│                    API LAYER (FastAPI)                        │

│   POST /analyze   GET /analyze/{id}   GET /listings/{dist}  │

│                   GET /health         GET /docs              │

└──────────────────┬──────────────────────────────────────────┘

│ Celery task queue

┌──────────────────▼──────────────────────────────────────────┐

│                  ASYNC WORKER LAYER (Celery + Redis)         │

│              run_analysis_pipeline task                      │

│              asyncio.run() → async orchestrator             │

└──────────────────┬──────────────────────────────────────────┘

│ LangGraph astream()

┌──────────────────▼──────────────────────────────────────────┐

│              AGENT ORCHESTRATION LAYER (LangGraph)           │

│                                                              │

│   AgentState (Pydantic BaseModel — shared memory bus)       │

│      │                                                       │

│   ┌──▼──────────┐  ┌──────────────┐  ┌──────────────────┐  │

│   │  Sourcing   │  │   Cleaning   │  │    Analyst       │  │

│   │   Agent     │→ │    Agent     │→ │    Agent         │  │

│   │             │  │              │  │                  │  │

│   │ Brave Search│  │ normalizer.py│  │ quant_tools.py   │  │

│   │ MCP Server  │  │ + LiteLLM   │  │ + LiteLLM        │  │

│   └─────────────┘  └──────────────┘  └──────────────────┘  │

│                                              │               │

│                                      ┌───────▼──────────┐   │

│                                      │   Risk Agent     │   │

│                                      │                  │   │

│                                      │compliance_tools  │   │

│                                      │.py + LiteLLM    │   │

│                                      └───────┬──────────┘   │

│                                              │               │

│                                      ┌───────▼──────────┐   │

│                                      │  Report Node     │   │

│                                      │  (assembles      │   │

│                                      │  final report)   │   │

│                                      └──────────────────┘   │

└──────────────────────────────────────────────────────────────┘

│

┌──────────────────▼──────────────────────────────────────────┐

│                    TOOL LAYER (MCP Servers)                   │

│                                                              │

│   PostgreSQL MCP Server          Brave Search MCP Server    │

│   ├── create_analysis_run        ├── search_real_estate     │

│   ├── insert_raw_listings        └── search_market_news     │

│   ├── insert_cleaned_listings                               │

│   ├── get_price_benchmarks                                  │

│   ├── insert_compliance_flags                               │

│   └── load_mock_data                                        │

└──────────────────────────────────────────────────────────────┘

│

┌──────────────────▼──────────────────────────────────────────┐

│                    DATA LAYER                                 │

│                                                              │

│   PostgreSQL 16 + TimescaleDB                               │

│   ├── raw_listings          (sourcing output)               │

│   ├── cleaned_listings      (normalization output)          │

│   ├── compliance_flags      (risk agent output)             │

│   ├── analysis_runs         (pipeline metadata)             │

│   └── price_history         (TimescaleDB hypertable)        │

│                             (time-series price tracking)    │

│                                                              │

│   Redis 7                                                   │

│   └── Celery broker + result backend                        │

└──────────────────────────────────────────────────────────────┘

### Data Flow: Request Lifecycle

Client posts POST /analyze with district list

│
FastAPI generates run_id, queues Celery task → returns 202

│
Celery worker picks up task, calls asyncio.run()

│
Async orchestrator: initialize_pool() → build_graph()

│
LangGraph streams through 4 agent nodes

│
Each node returns partial AgentState update

│
Final state assembled → investment_report generated

│
Report persisted to PostgreSQL analysis_runs table

│
Client polls GET /analyze/{run_id} → receives report

---

## 🤖 Agent Topology
┌─────────────────┐
                │   START NODE    │
                │  (initializes   │
                │   AgentState)   │
                └────────┬────────┘
                         │
                         ▼
                ┌─────────────────┐
                │ SOURCING AGENT  │──── error ──► ERROR NODE
                │                 │
                │ Tools:          │
                │ search_real_    │
                │ estate (MCP)    │
                └────────┬────────┘
                         │ raw_listings []
                         ▼
                ┌─────────────────┐
                │ CLEANING AGENT  │──── error ──► ERROR NODE
                │                 │
                │ Pass 1:         │
                │ normalizer.py   │
                │ (deterministic) │
                │                 │
                │ Pass 2:         │
                │ LiteLLM         │
                │ (semantic)      │
                └────────┬────────┘
                         │ cleaned_listings []
                         ▼
                ┌─────────────────┐
                │ ANALYST AGENT   │──── error ──► ERROR NODE
                │                 │
                │ Tools:          │
                │ get_price_      │
                │ benchmarks (DB) │
                │                 │
                │ quant_tools.py  │
                │ (stats, z-score │
                │  outlier detect)│
                └────────┬────────┘
                         │ benchmarks, undervalued_ids
                         ▼
                ┌─────────────────┐
                │  RISK AGENT     │──── error ──► ERROR NODE
                │                 │
                │ compliance_     │
                │ tools.py:       │
                │ ├─ RERA check   │
                │ ├─ Waqf flag    │
                │ ├─ Foreign own. │
                │ └─ VAT check    │
                └────────┬────────┘
                         │ compliance_flags []
                         ▼
                ┌─────────────────┐
                │  REPORT NODE    │
                │                 │
                │  Assembles:     │
                │  ├─ benchmarks  │
                │  ├─ undervalued │
                │  └─ compliance  │
                └────────┬────────┘
                         │ investment_report (str)
                         ▼
                       END

### Agent Responsibility Matrix

| Agent | LLM Role | Deterministic Role |
|-------|----------|-------------------|
| Sourcing | Query formulation, result structuring | Mock data filtering by district |
| Cleaning | Arabic→English translation, type inference | Price parsing, area conversion, RERA regex |
| Analyst | Investment narrative, opportunity ranking | Benchmark fallback from state (no LLM math) |
| Risk | Flag generation from listing fields | `compliance_tools.py` rule evaluation |

**Core Design Rule:**
> If a task relies on a fixed mathematical constant, defined syntactic
> pattern, or exact lookup — it is deterministic Python.
> If it requires semantic comprehension or multilingual reasoning
> — it is routed to the LLM.

---

## 🛠️ Tech Stack

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| **Orchestration** | LangGraph 1.x (Subgraph pattern) | Deterministic state-machine control, audit trails, conditional routing |
| **LLM Abstraction** | LiteLLM | Provider-agnostic — swap Groq/Gemini/Ollama via single `.env` line |
| **Primary LLM** | Groq / llama-3.1-70b-versatile | Free tier, GPT-4 class reasoning, 6K tokens/min |
| **Backup LLM** | Gemini 1.5 Flash | 1M tokens/day free, zero-cost fallback |
| **State Schema** | Pydantic v2 BaseModel | Checkpoint serialization safety (vs TypedDict runtime erasure) |
| **Database** | PostgreSQL 16 + TimescaleDB | Time-series price depreciation modeling via hypertables |
| **MCP Servers** | Custom Python MCP SDK servers | Auditable tool layer between agents and infrastructure |
| **Evaluation** | Ragas + LangSmith | Generation faithfulness + answer relevance scoring |
| **API** | FastAPI 0.111+ | Async-first, lifespan context manager, OpenAPI auto-docs |
| **Task Queue** | Celery 5 + Redis 7 | Long-running pipeline runs (1-3 min) need separate worker process |
| **Monitoring** | Flower + LangSmith | Celery task telemetry + agent trace observability |
| **Dashboard** | Streamlit | Python-native MVP — communicates via HTTP only |
| **Dependencies** | Poetry 2.x (PEP 621) | Lockfile determinism, in-project `.venv`, Docker-compatible |
| **Containers** | Docker Compose | Single-command local stack (DB + Redis + API + Worker + Flower) |
| **Deployment** | Render.com | Free managed PostgreSQL + Redis + Docker services, no credit card |

### Zero-Cost Provider Map

| Service | Provider | Free Limit |
|---------|----------|-----------|
| LLM Inference | Groq | 6,000 tokens/min |
| LLM Backup | Google Gemini Flash | 1M tokens/day |
| Observability | LangSmith | 5,000 traces/month |
| Web Search | Brave Search API | 2,000 queries/month |
| Database (cloud) | Render.com PostgreSQL | 1GB free forever |
| Redis (cloud) | Render.com Redis | Free tier |
| Deployment | Render.com | Free web + worker services |

---

## 📁 Project Structure

KSA-Real-Estate-Agent/

│

├── .claude/

│   └── CLAUDE.md                    # Execution Layer contract for Claude Code

│

├── src/

│   ├── core/                        # Shared infrastructure — imported by all agents

│   │   ├── config.py                # Pydantic Settings v2 — single env var source of truth

│   │   ├── exceptions.py            # Custom exception hierarchy (KSAAgentError tree)

│   │   ├── logging_setup.py         # Structured JSON logging (JSONFormatter)

│   │   ├── state.py                 # LangGraph AgentState + RawListing + CleanedListing

│   │   └── database.py              # asyncpg connection pool singleton

│   │

│   ├── agents/

│   │   ├── sourcing/

│   │   │   ├── agent.py             # sourcing_node() — LangGraph node function

│   │   │   └── prompts.py           # SOURCING_SYSTEM_PROMPT + build_sourcing_prompt()

│   │   ├── cleaning/

│   │   │   ├── agent.py             # cleaning_node() — two-pass hybrid approach

│   │   │   ├── prompts.py           # Semantic-only prompt (translation, inference)

│   │   │   └── normalizer.py        # Deterministic parsing (price, area, district, RERA)

│   │   ├── analyst/

│   │   │   ├── agent.py             # analyst_node() — benchmark + undervalue detection

│   │   │   └── prompts.py           # ANALYST_OUTPUT_SCHEMA + build_analyst_prompt()

│   │   └── risk/

│   │       ├── agent.py             # risk_node() — compliance flag generation

│   │       └── prompts.py           # RISK_SYSTEM_PROMPT with Saudi regulatory rules

│   │

│   ├── tools/

│   │   ├── quant_tools.py           # Stats: z-score, district benchmarks, opportunity rank

│   │   └── compliance_tools.py      # Rules: RERA, Waqf, foreign ownership, VAT

│   │

│   ├── mcp_servers/

│   │   ├── postgres_server/

│   │   │   ├── schemas.py           # SQL DDL: 5 tables + TimescaleDB hypertable

│   │   │   ├── repository.py        # ListingRepository — Repository Pattern

│   │   │   └── server.py            # MCP server: 8 tools exposed to agents

│   │   └── search_server/

│   │       └── server.py            # Brave Search MCP: 2 tools, auto Riyadh context

│   │

│   ├── graph/

│   │   ├── builder.py               # build_graph() — full LangGraph assembly

│   │   ├── router.py                # Conditional edge routing functions

│   │   └── checkpointer.py          # MemorySaver (dev) / AsyncPostgresSaver (prod)

│   │

│   ├── api/

│   │   ├── main.py                  # FastAPI app — lifespan, CORS, router registration

│   │   ├── schemas.py               # Request/response Pydantic v2 models

│   │   └── routes/

│   │       ├── analysis.py          # POST /analyze, GET /analyze/{run_id}

│   │       └── listings.py          # GET /listings/{district}

│   │

│   ├── workers/

│   │   ├── celery_app.py            # Celery app factory + configuration

│   │   └── tasks.py                 # run_analysis_pipeline — asyncio.run() pattern

│   │

│   └── dashboard/

│       └── app.py                   # Streamlit MVP — 4 tabs, HTTP-only API client

│

├── evals/

│   ├── datasets/

│   │   ├── cleaning_eval_dataset.json   # 15 golden records (translation, normalization)

│   │   ├── analyst_eval_dataset.json    # 10 golden records (benchmarks, undervalue)

│   │   └── risk_eval_dataset.json       # 10 golden records (compliance flags)

│   ├── judges/

│   │   ├── faithfulness.py          # FaithfulnessJudge — Ragas faithfulness metric

│   │   └── relevance.py             # AnswerRelevanceJudge — Ragas relevance + fastembed

│   └── runner.py                    # CI/CD eval orchestrator — exits 1 on FAIL

│

├── data/

│   ├── mock/

│   │   └── riyadh_listings.json     # 50 realistic listings, 8 districts, injected issues

│   └── migrations/

│       └── runner.py                # Standalone schema migration (no Alembic)

│

├── tests/

│   ├── conftest.py                  # Shared fixtures: sample listings, agent state

│   ├── unit/

│   │   ├── test_exceptions.py       # Exception hierarchy + context tests

│   │   ├── test_state.py            # AgentState, RawListing, CleanedListing tests

│   │   ├── test_logging.py          # JSONFormatter, setup_logging, get_logger tests

│   │   ├── test_database.py         # Pool singleton + repository (mocked asyncpg)

│   │   ├── test_normalizer.py       # 21 deterministic parsing tests

│   │   ├── test_quant_tools.py      # 7 statistical analysis tests

│   │   ├── test_compliance_tools.py # 8 compliance rule tests

│   │   ├── test_evals.py            # 7 eval infrastructure tests (mocked Ragas)

│   │   └── test_api.py              # 8 FastAPI endpoint tests (TestClient)

│   └── integration/

│       ├── test_mcp_servers.py      # MCP tool registration + handler tests

│       └── test_graph.py            # Graph compilation + routing tests

│

├── docs/

│   └── architecture.md              # Architecture documentation (progressive)

│

├── Dockerfile                       # python:3.10-slim, Poetry, non-root user

├── docker-compose.yml               # db + redis + flower + api + worker

├── render.yaml                      # Render.com deployment manifest

├── pyproject.toml                   # PEP 621 compliant, Poetry 2.x

├── .env.example                     # All env vars with signup links

├── .gitignore                       # .venv, .env, pycache, logs

└── README.md                        # This file

---

## 🚀 Quick Start

### Prerequisites

- Python 3.10.10
- Docker Desktop (for PostgreSQL + Redis + TimescaleDB)
- Poetry 2.x (`pip install poetry`)

### 1. Clone and Install

```bash
git clone https://github.com/yourusername/KSA-Real-Estate-Agent.git
cd KSA-Real-Estate-Agent

# Configure Poetry to create .venv inside project
poetry config virtualenvs.in-project true

# Install all dependencies
poetry install

# Activate virtual environment
# Windows:
.\.venv\Scripts\Activate.ps1
# macOS/Linux:
source .venv/bin/activate
```

### 2. Configure Environment

```bash
# Copy the example env file
cp .env.example .env

# Edit .env and add your API keys:
# Required:
#   GROQ_API_KEY      → console.groq.com (free, no credit card)
#   LANGSMITH_API_KEY → smith.langchain.com (free dev tier)
#   BRAVE_SEARCH_API_KEY → brave.com/search/api (2K/month free)
```

### 3. Start Infrastructure

```bash
# Start PostgreSQL (TimescaleDB) + Redis + Flower monitoring
docker-compose up db redis flower -d

# Verify services are healthy
docker-compose ps
```

### 4. Run Database Migrations

```bash
python data/migrations/runner.py
# Expected: Migration completed successfully
```

### 5. Load Mock Data

```bash
python -c "
import asyncio
from src.core.database import initialize_pool, close_pool
from src.mcp_servers.postgres_server.repository import ListingRepository

async def load():
    await initialize_pool()
    repo = ListingRepository()
    result = await repo.load_mock_data('data/mock/riyadh_listings.json', 'seed-run-001')
    print(f'Loaded: {result}')
    await close_pool()

asyncio.run(load())
"
```

### 6. Start API Server

```bash
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

# Verify:
# API docs:    http://localhost:8000/docs
# Health:      http://localhost:8000/health
```

### 7. Start Celery Worker (new terminal)

```bash
celery -A src.workers.celery_app.celery_app worker \
  --loglevel=info --concurrency=2
```

### 8. Start Streamlit Dashboard (new terminal)

```bash
streamlit run src/dashboard/app.py
# Opens: http://localhost:8501
```

### 9. Run Full Docker Stack (Alternative)

```bash
# Start everything at once
docker-compose up --build

# Services:
# FastAPI:    http://localhost:8000/docs
# Streamlit:  http://localhost:8501
# Flower:     http://localhost:5555
# PostgreSQL: localhost:5432
# Redis:      localhost:6379
```

---

## 📡 API Reference

### POST /analyze

Submit a new analysis pipeline run. Returns immediately with `run_id`.

```bash
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "districts": ["Olaya", "KAFD", "Al_Malqa"],
    "max_listings_per_district": 10,
    "use_mock_data": true
  }'
```

```json
{
  "run_id": "a3f8c2d1-...",
  "status": "queued",
  "status_url": "/analyze/a3f8c2d1-...",
  "message": "Analysis pipeline queued successfully"
}
```

### GET /analyze/{run_id}

Poll for pipeline status and retrieve completed report.

```bash
curl http://localhost:8000/analyze/a3f8c2d1-...
```

```json
{
  "run_id": "a3f8c2d1-...",
  "status": "complete",
  "current_phase": "complete",
  "investment_report": "═══ RIYADH REAL ESTATE INVESTMENT INTELLIGENCE REPORT ═══\n...",
  "error": null
}
```

**Status values:** `queued` → `running` → `complete` | `failed`

### GET /listings/{district}

Retrieve normalized listings for a specific district.

```bash
curl "http://localhost:8000/listings/Olaya?limit=20"
```

```json
{
  "district": "Olaya",
  "total": 8,
  "avg_price_per_sqm": 13250.0,
  "listings": [...]
}
```

**Valid districts:** `Olaya`, `Al_Malqa`, `Al_Nakheel`, `Al_Rawdah`,
`KAFD`, `Al_Naseem`, `Al_Shifa`, `Al_Wurud`

### GET /health

```json
{
  "status": "healthy",
  "database": "healthy",
  "redis": "healthy",
  "version": "0.1.0"
}
```

---

## 📊 Evaluation Suite

The Ragas evaluation suite provides quantitative quality assurance
across three agent categories:

```bash
# Run full evaluation suite (requires GROQ_API_KEY in .env)
python -m evals.runner
```
═══════════════════════════════════════════

RAGAS EVALUATION SUITE

═══════════════════════════════════════════

Overall Status: PASS
Metric Results:

cleaning_faithfulness:  0.89  [PASS ≥0.75]

analyst_faithfulness:   0.84  [PASS ≥0.75]

analyst_relevance:      0.91  [PASS ≥0.75]

risk_faithfulness:      0.87  [PASS ≥0.75]

═══════════════════════════════════════════



## 🗺️ Roadmap

| Phase | Description | Status |
|-------|-------------|--------|
| Phase 0 | Scaffolding: Poetry, Docker Compose, CLAUDE.md | ✅ |
| Phase 1 | Core layer: config, exceptions, logging, state | ✅ |
| Phase 2 | Data layer: asyncpg, TimescaleDB, MCP servers | ✅ |
| Phase 3 | Agent topology: LangGraph, 4 agents, tools | ✅ |
| Phase 4 | Ragas evaluation suite, golden datasets, CI runner | ✅ |
| Phase 5 | FastAPI, Celery, Streamlit, Docker, Render.com | ✅ |
| Phase 6 | E2E smoke test, live deployment, portfolio packaging | 🚧 |
| Phase 7 | Next.js dashboard upgrade, advanced analytics | 📋 |
| Phase 8 | Live data integration (Aqar.sa, Bayut.sa) | 📋 |

NOTE: Currently, on phase 5, will move to phase 6 for deployment and then Phase 7 and Phase 8 afterwards.

## 👨‍💻 Author

Built as a AI Engineering portfolio project targeting the
GCC technology market, demonstrating production-grade agentic AI
system design with enterprise coding standards by Aaish Faisal Hameedi.

---

*Built with LangGraph · LiteLLM · FastAPI · PostgreSQL + TimescaleDB · Ragas*
