# 🛡️ LawShield — Indian Legal AI Platform

> **A full-stack, production-grade multi-agent AI platform** for Indian law — combining RAG, PII masking, LangGraph orchestration, vector+lexical hybrid search, real-time streaming, and a three-tier observability stack.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Architecture at a Glance](#2-architecture-at-a-glance)
3. [Tech Stack](#3-tech-stack)
4. [Directory Structure](#4-directory-structure)
5. [Service Breakdown](#5-service-breakdown)
6. [Conversation Flow — End to End](#6-conversation-flow--end-to-end)
7. [Multi-Agent Graph (LangGraph)](#7-multi-agent-graph-langgraph)
8. [RAG Pipeline — Deep Dive](#8-rag-pipeline--deep-dive)
9. [PII Masking System](#9-pii-masking-system)
10. [Memory Architecture](#10-memory-architecture)
11. [LLM Provider Layer](#11-llm-provider-layer)
12. [SSE Streaming Architecture](#12-sse-streaming-architecture)
13. [Observability Stack](#13-observability-stack)
14. [Database Schema](#14-database-schema)
15. [API Reference](#15-api-reference)
16. [Environment Variables](#16-environment-variables)
17. [Running Locally](#17-running-locally)
18. [Interview Q&A — Deep Technical Questions]


(#18-interview-qa--deep-technical-questions)

---

## 1. Project Overview

**LawShield** is an AI-powered legal assistant tailored for **Indian law**. Users can:

- **Chat** with Harvey (the AI), who specializes in Indian statutes, Supreme Court judgments, and High Court decisions.
- **Upload legal documents** (PDF, DOCX, TXT) and ask targeted questions grounded strictly in those documents.
- Rely on **automatic PII masking** — names, Aadhaar numbers, PANs, phone numbers, etc., are masked before being sent to any LLM, and restored in the final answer.
- Receive **source-grounded responses** — the system refuses to hallucinate; if the document doesn't contain the answer, it says so explicitly.

---

## 2. Architecture at a Glance

```
┌─────────────────────────────────────────────────────────────────────┐
│                         USER BROWSER                                │
│  React + Vite (port 5173)                                           │
│  • Chat UI with SSE streaming                                       │
│  • Document upload panel                                            │
│  • Thread management sidebar                                        │
└────────────────────────────┬────────────────────────────────────────┘
                             │ HTTP / SSE
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      NODE.JS BACKEND (port 3000)                    │
│  Express + Prisma ORM                                               │
│  • JWT Authentication                                               │
│  • Thread & Message persistence (PostgreSQL)                        │
│  • Document upload proxy (→ AI Service)                             │
│  • SSE streaming proxy (→ AI Service)                               │
└────────────────────────────┬────────────────────────────────────────┘
                             │ HTTP / SSE (internal)
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    PYTHON AI SERVICE (port 8000)                    │
│  FastAPI + LangGraph + LangChain                                    │
│                                                                     │
│  ┌─────────────┐    ┌──────────────────────────────────────────┐   │
│  │  PII Masking│───▶│       ChatService (Orchestrator)         │   │
│  │  (Presidio) │    │  mask → build_state → stream_graph →    │   │
│  └─────────────┘    │  restore                                 │   │
│                     └──────────────┬─────────────────────────-┘   │
│                                    │                                │
│                     ┌──────────────▼───────────────────────────┐   │
│                     │      LangGraph Multi-Agent Graph          │   │
│                     │  supervisor → [planner→research→         │   │
│                     │   drafting→citation→review] |            │   │
│                     │   contract | summarizer | compliance |   │   │
│                     │   calculator | reasoning | qa | rag      │   │
│                     └──────────────────────────────────────────┘   │
│                                                                     │
│  ┌──────────────────┐  ┌────────────────┐  ┌────────────────────┐  │
│  │  Qdrant (Vector) │  │ Elasticsearch  │  │ PostgreSQL (Facts) │  │
│  └──────────────────┘  └────────────────┘  └────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| **Frontend** | React 18, Vite, React Router v6, TailwindCSS | UI, routing, SSE client |
| **Backend** | Node.js, Express 5, Prisma ORM, JWT, Multer | API gateway, auth, DB proxy |
| **AI Service** | Python 3.12, FastAPI, Uvicorn | AI orchestration REST service |
| **Agent Framework** | LangGraph, LangChain | Multi-agent state machine |
| **LLM Providers** | Groq (Llama 3.1), OpenAI (GPT-4o-mini), Gemini 2.5 Flash, Claude 3 Haiku | Pluggable LLMs |
| **PII Detection** | Microsoft Presidio + spaCy (`en_core_web_lg`) | Named-entity recognition |
| **Vector DB** | Qdrant | Semantic document + conversation search |
| **Lexical Search** | Elasticsearch | BM25 keyword retrieval |
| **Relational DB** | PostgreSQL | Users, threads, messages, long-term facts |
| **Embeddings** | BGE-small-en-v1.5 (384-dim) | Document & conversation vectors |
| **Observability** | OpenTelemetry, Prometheus, structured logging | Tracing, metrics, logs |

---

## 4. Directory Structure

```
lawShield/
├── start.sh                    # One-command launcher for all 3 services
├── frontend/                   # React + Vite SPA
│   └── src/
│       ├── pages/
│       │   ├── WorkspacePage.jsx   # Main app shell, chat UI, sidebar
│       │   ├── AuthPage.jsx        # Login / Register
│       │   └── LandingPage.jsx     # Public landing
│       ├── context/AuthContext.jsx # JWT auth state
│       └── App.jsx                 # Routes definition
│
├── backend/                    # Node.js Express API gateway
│   ├── server.js               # App bootstrap, CORS, route mounting
│   ├── routes/
│   │   ├── auth.js             # POST /api/auth/register, /login
│   │   ├── threads.js          # CRUD for conversation threads
│   │   ├── chat.js             # /api/chat/ and /api/chat/stream
│   │   └── documents.js        # Document upload & metadata
│   ├── middleware/auth.js       # JWT verification middleware
│   ├── lib/prisma.js            # Prisma singleton
│   └── prisma/schema.prisma    # Database schema
│
└── ai_service/                 # Python FastAPI AI engine
    ├── main.py                 # FastAPI app, CORS, router mounting
    ├── chat/
    │   ├── router.py           # /chat/ and /chat/stream endpoints
    │   └── chat_service.py     # Orchestrates masking + graph + memory
    ├── graph/
    │   ├── graph.py            # LangGraph StateGraph definition
    │   ├── state.py            # AgentState TypedDict
    │   └── conditions/routing.py  # Route supervisor, route reviewer
    ├── agents/                 # 13 specialist agent nodes
    │   ├── supervisor/         # Routes to correct specialist
    │   ├── planner/            # Step-by-step research plan
    │   ├── research/           # Web/document research
    │   ├── drafting/           # Legal document drafting
    │   ├── citation/           # Citation injection
    │   ├── review/             # Quality gate (approve/reject)
    │   ├── contract/           # Contract analysis
    │   ├── summarizer/         # Document summarization
    │   ├── compliance/         # Compliance checking
    │   ├── calculator/         # Legal fee/penalty calculations
    │   ├── reasoning/          # Multi-step legal reasoning
    │   ├── qa/                 # Lightweight Q&A
    │   └── rag/                # RAG-grounded document Q&A
    ├── rag/
    │   ├── pipelines.py        # Ingest + Self-RAG pipeline
    │   ├── chunking.py         # Heading-aware legal chunker
    │   ├── embedding.py        # BGE embedding wrapper
    │   ├── retrieval.py        # Qdrant + ES client helpers
    │   ├── reranker.py         # TF-IDF + specificity reranker
    │   ├── hybrid/search.py    # Vector + BM25 hybrid search (RRF)
    │   ├── adaptive/           # Query routing + rewriting
    │   ├── self_rag/           # Grounding evaluator graph
    │   ├── citation/           # Citation generator
    │   └── metadata/           # Filter extraction
    ├── masking/
    │   ├── masking_pipeline.py # Core mask/restore functions
    │   ├── ner.py              # Presidio AnalyzerEngine setup
    │   ├── regex.py            # Custom Indian PII regex recognizers
    │   └── replacement.py      # MaskingState (placeholder ↔ original)
    ├── memory/
    │   ├── conversation.py     # Sliding-window in-memory store
    │   ├── long_term.py        # LLM fact extraction → PostgreSQL
    │   ├── vector.py           # Conversation → Qdrant embeddings
    │   └── session.py          # Session utilities
    ├── llm/
    │   └── providers/
    │       ├── factory.py      # Provider selection + rate-limit retry
    │       └── base.py         # BaseLLMProvider interface
    └── observability/
        ├── __init__.py         # Package exports
        ├── monitoring.py       # initialize_observability, middleware
        ├── tracing.py          # OpenTelemetry setup + trace_agent()
        ├── metrics.py          # Prometheus counters/histograms/gauges
        └── logs.py             # Structured JSON logging setup
```

---

## 5. Service Breakdown

### 5.1 Frontend (React + Vite)

**Single Page Application** built with React 18 and Vite. All app views live in `WorkspacePage.jsx` as nested route components mounted inside a `Shell` layout.

**Key components:**

| Component | Role |
|---|---|
| `Shell` | Persistent sidebar (nav + recent threads), header bar, mobile drawer |
| `Overview` | Dashboard — quick-action cards, hero prompt box |
| `Chat` | Full SSE-streaming chat interface with markdown rendering |
| `MarkdownMessage` | Lightweight in-house markdown renderer (headers, lists, code blocks, blockquotes) — no external lib |

**Chat flow on the frontend:**
1. User types and hits Enter → `send()` is called.
2. If no thread exists, a `POST /api/threads` creates one; the URL is updated to `?thread=<id>`.
3. `fetch('/api/chat/stream', ...)` opens an SSE connection.
4. The response stream is parsed event-by-event:
   - `[Node: supervisor]` — progress ping, silently consumed.
   - `[FINAL]` — sets `capturingFinal = true`; subsequent chunks accumulate in `finalText`.
   - `[DONE]` — commits `finalText` as a new message in state; clears the live preview.
   - `[ERROR]` — displays an error bubble.
5. If the stream fails entirely, the code falls back to `POST /api/chat/` (non-streaming).

---

### 5.2 Backend (Node.js / Express)

Acts as a **secure API gateway** between the browser and the Python AI service.

**Why a separate backend?**
- Enforces **JWT authentication** before any AI call is made.
- Persists all messages in **PostgreSQL** via Prisma — the AI service is stateless.
- Proxies the **SSE stream** from the AI service to the browser without buffering the full response.
- Handles **document uploads** via Multer (memory storage) and re-posts them as `multipart/form-data` to the AI service.

**Route map:**

| Route | Method | Auth | Description |
|---|---|---|---|
| `/api/auth/register` | POST | No | Create account (bcrypt hash) |
| `/api/auth/login` | POST | No | Returns JWT |
| `/api/threads` | GET | Yes | List all threads for user |
| `/api/threads` | POST | Yes | Create new thread |
| `/api/threads/:id` | GET | Yes | Fetch thread + messages |
| `/api/threads/:id` | DELETE | Yes | Delete thread (cascade) |
| `/api/chat/` | POST | Yes | Non-streaming chat proxy |
| `/api/chat/stream` | POST | Yes | SSE streaming proxy |
| `/api/documents` | GET | Yes | List user documents |
| `/api/documents/upload-and-ingest` | POST | Yes | Upload + ingest to vector DB |
| `/api/documents/:id` | DELETE | Yes | Delete document record |

---

### 5.3 AI Service (Python / FastAPI)

The **brain** of LawShield. A FastAPI application running with Uvicorn that hosts the multi-agent graph, RAG pipeline, PII masking, and observability stack.

**Startup sequence (`main.py`):**
1. `load_dotenv()` — loads API keys and config.
2. `initialize_observability()` — sets up tracing, logging, and metrics before any request arrives.
3. CORS middleware is added (allows Node backend and Vite dev server).
4. `ObservabilityMiddleware` records HTTP request counts and durations automatically.
5. All routers (`chat`, `llm`, `documents`, `rag`, `workflow`, `evaluation`, `communication`) are mounted.

---

## 6. Conversation Flow — End to End

```
User types "What are the penalties under POCSO Act?"
          │
          ▼
[Frontend] send() → POST /api/chat/stream  (SSE)
          │
          ▼
[Backend]  auth middleware validates JWT
           thread ownership verified
           user message saved to DB → Message(role=USER)
           history array assembled from DB messages
          │
          ▼
[Backend]  opens raw Node.js http.request to Python /chat/stream
          │
          ▼
[Python ChatService.stream_chat()]
  1. _process_history() — masks PII in all previous messages
  2. mask_text(current message) → passes through (no PII here)
  3. _build_system_message() — async:
       • get_long_term_facts(session_id) → pulled from PostgreSQL
       • search_vector_memory(session_id, query, top_k=2) → Qdrant
       • builds Harvey's Indian law system prompt enriched with context
  4. Initial AgentState built with full message history
  5. graph.astream(state) — starts the LangGraph pipeline:
       │
       ▼
    [supervisor node]
      • LLM classifies query → routes to "reasoning" agent
      • yields: "data: [Node: supervisor]\n\n"
       │
       ▼
    [reasoning node]
      • Multi-step legal chain-of-thought
      • Produces: final_answer = "Under POCSO Act..."
      • yields: "data: [Node: reasoning]\n\n"
       │
       ▼
    ChatService catches final_answer from terminal node
  6. restore_text(final_answer, masking_state)
     → replaces any <PERSON_1> placeholders with real names
  7. yield "[FINAL]"
  8. yield restored_answer
  9. yield "[DONE]"
  10. _commit_memory_background() (fire-and-forget):
       • extract_and_save_facts() → LLM extracts facts → PostgreSQL
       • save_to_vector_memory() → embeds exchange → Qdrant
          │
[Backend]  SSE events forwarded to frontend in real time
           On [DONE]: saves assistant message to DB → Message(role=ASSISTANT)
           Bumps thread.updatedAt
          │
[Frontend] Renders streaming text token-by-token
           On [DONE]: commits finalText to React state
```

---

## 7. Multi-Agent Graph (LangGraph)

LangGraph is used to build a **compiled StateGraph** — a directed graph where each node is an agent and edges define routing rules.

### 7.1 AgentState

```python
class AgentState(TypedDict, total=False):
    messages: Annotated[List[BaseMessage], operator.add]  # append-only
    next_node: str       # supervisor's routing decision
    plan: str            # step-by-step plan from planner
    research_data: List[str]
    draft_content: str
    citations: List[str]
    review_status: str   # "approved" | "rejected"
    contract_analysis: str
    compliance_report: str
    summary: str
    calculation_result: str
    reasoning_output: str
    reasoning_confidence: float
    reasoning_iterations: int
```

`total=False` allows nodes to return **partial state updates** — LangGraph merges them without `KeyError`. The `messages` field uses `operator.add` so each node **appends** rather than overwrites the full conversation.

### 7.2 Supervisor Node

The supervisor is the **entry point** of every request. It:
1. Reads the latest user message.
2. Makes a single LLM call to classify the query intent.
3. Sets `next_node` to one of: `planner`, `contract`, `summarizer`, `compliance`, `calculator`, `reasoning`, `qa`, `rag`, or `FINISH`.
4. `FINISH` means the supervisor can answer directly (greetings, small talk) — `ChatService._direct_response()` handles this.

### 7.3 Specialist Agents

| Agent | Triggered when | Does |
|---|---|---|
| **planner** | Complex multi-step legal research | Produces a structured research plan |
| **research** | After planner | Gathers evidence, case law, statutes |
| **drafting** | After research | Drafts the legal document/brief |
| **citation** | After drafting | Injects statute citations and case references |
| **review** | After citation | Quality gate: approves or sends back to planner |
| **contract** | Contract review/analysis queries | Analyzes contract clauses |
| **summarizer** | Summarization requests | Condenses long documents |
| **compliance** | Regulatory compliance checks | Maps requirements to rules |
| **calculator** | Fee/penalty/date calculations | Computes legal numbers |
| **reasoning** | Case analysis, legal reasoning | Multi-step chain-of-thought over Indian law |
| **qa** | Direct factual legal questions | Lightweight, fast Q&A |
| **rag** | Questions about uploaded documents | Self-RAG pipeline over vector store |

### 7.4 Routing Logic

**Supervisor → specialists** (conditional edges):
```python
route_supervisor(state) -> str
# Reads state["next_node"] set by the supervisor LLM call
```

**Review → planner or END** (conditional edges):
```python
route_reviewer(state) -> str
# review_status == "rejected" → "planner" (retry loop)
# review_status == "approved" → "__end__"
```

All terminal nodes (`contract`, `summarizer`, `compliance`, `calculator`, `reasoning`, `qa`, `rag`) have direct edges to `END` — no re-routing.

---

## 8. RAG Pipeline — Deep Dive

### 8.1 Document Ingestion

```
[Browser] → multipart/form-data → [Node backend] → multipart/form-data → [Python /documents/upload-and-ingest]
```

Python extracts text (PDF via PyMuPDF/pdfplumber, DOCX via python-docx, TXT directly), then:
1. **Chunks** the text (heading-aware).
2. **Embeds** each chunk (BGE-small-en-v1.5, 384-dim).
3. **Indexes** into Qdrant (vector search).
4. **Indexes** into Elasticsearch (lexical BM25 search) if available.
5. Returns `{"status": "success", "chunks_indexed": N}`.

### 8.2 Chunking Strategy

`chunking.py` implements a **heading-aware legal document chunker**:

1. Detects section/clause headings via regex: `Clause 10 — AI SYSTEMS`, `Section 5: Confidentiality`, `ARTICLE IV`.
2. Splits the document at each heading — each clause becomes its own section.
3. Sections ≤ 1,400 characters → stored as one chunk.
4. Sections > 1,400 characters → sub-split with `RecursiveCharacterTextSplitter` (chunk_size=1200, overlap=200), each sub-chunk prefixed with `[Clause Title (Cont.)]`.
5. Every chunk gets metadata: `chunk_id`, `section_title`, `section_number`, `prev_chunk_id`, `next_chunk_id` (for neighbor-aware retrieval).

**Why this matters:** Legal documents are clause-structured. Splitting on clause boundaries prevents a chunk from containing half of "Clause 4 — Payment Terms" and half of "Clause 5 — Termination," which would confuse the retriever.

### 8.3 Hybrid Search

`rag/hybrid/search.py` runs **two retrievers in parallel** and merges results:

1. **Qdrant vector search** — cosine similarity on BGE-384 embeddings → semantic understanding.
2. **Elasticsearch BM25** — keyword/token overlap → exact term matching.

Results are merged using **Reciprocal Rank Fusion (RRF)**:
```
rrf_score(doc) = Σ 1 / (k + rank_i)   where k=60
```
This gives a final ranked list that benefits from both semantic and lexical retrieval without score normalization.

### 8.4 Reranking

After hybrid search, `reranker.py` applies a **legal-specificity reranker**:

- **Base score**: TF-IDF similarity between query tokens and chunk text.
- **Domain specificity boost**: chunks whose section title/body matches domain terms get a 1.5–2.0× multiplier.
- **Exception boost**: when query asks "what are the exceptions?", chunks with "provided that", "unless", "subject to" get +0.25–0.5.
- **Section title match boost**: direct query keyword matches in section headings add +0.15 per token.

### 8.5 Self-RAG Evaluation Loop

The `rag` agent uses a **Self-RAG StateGraph** (inner graph) before returning any answer:

```
retrieve → grade_documents → [all irrelevant? → rewrite query → retrieve again]
         → generate answer → check_hallucination → [hallucinated? → regen strict prompt]
         → check_answer_relevance → [not relevant? → rewrite query]
         → return answer
```

Each step is a grading LLM call:
- **grade_documents**: Is this retrieved chunk actually relevant?
- **check_hallucination**: Does the answer contain claims not in retrieved chunks?
- **check_answer_relevance**: Does the answer actually address the question?

Max retries: 2 rewrites, 2 regenerations. If exhausted → hard refusal.

### 8.6 Anti-Hallucination Hardening

- **Hard refusal string** returned whenever `context_used` is empty.
- `_direct_llm_answer()` refuses to run without `context_str` — no raw LLM answers for legal questions.
- Separate system prompts per path: `_RAG_SYSTEM_PROMPT`, `_WEB_SEARCH_SYSTEM_PROMPT`, `_STRICT_REGEN_SYSTEM_PROMPT` — each explicitly forbids inventing statutes or case references.

---

## 9. PII Masking System

LawShield never sends raw user data to any LLM. All messages pass through the masking pipeline before hitting the AI graph.

### 9.1 Detection Engine

`masking/ner.py` builds a **Microsoft Presidio AnalyzerEngine** (thread-safe lazy singleton via double-checked locking):
- Uses **spaCy `en_core_web_lg`** for NER (falls back to `en_core_web_sm` if not installed).
- Loads all Presidio built-in recognizers.
- Registers all custom Indian-law recognizers.
- Minimum confidence threshold: **0.35** (tunable to reduce false positives).

### 9.2 Indian-specific Entities

Custom regex recognizers (`masking/regex.py`) detect:

| Entity | Pattern |
|---|---|
| `AADHAAR_NUMBER` | 12-digit UID with optional spaces |
| `IN_PAN` | `[A-Z]{5}[0-9]{4}[A-Z]` |
| `IN_GSTIN` | 15-char GST Identification Number |
| `IN_VOTER_ID` | Electoral Photo ID Card |
| `IN_DRIVING_LICENCE` | State-prefixed DL number |
| `IN_PASSPORT` | Letter + 7 digits |
| `IN_IFSC` | 11-char bank branch code |
| `IN_PHONE_NUMBER` | +91 or 0 prefix mobile/STD |
| `IN_VEHICLE_REG` | Registration plates (e.g. MH01AB1234) |
| `BANK_ACCOUNT` | Account numbers (context-gated) |
| `DATE_OF_BIRTH` | Common Indian date formats |

Plus standard Presidio entities: `PERSON`, `EMAIL_ADDRESS`, `PHONE_NUMBER`, `CREDIT_CARD`, `ORGANIZATION`, `LOCATION`, `DATE_TIME`, `URL`, `IP_ADDRESS`, etc.

### 9.3 Masking Pipeline

```python
masked_text, state = mask_text(text, state)
```

Steps:
1. **Detect** — `analyzer.analyze(text, entities=ALL_ENTITIES, score_threshold=0.35)`
2. **Filter** — drop detections below threshold, skip single-char hits (prevents "I" → `<PERSON_1>`)
3. **Resolve overlaps** — greedy interval scheduling: higher-confidence span wins, dominated spans discarded
4. **Apply replacements** — right-to-left so replacing span [50:60] doesn't shift indices for span [20:30]
5. Each entity gets a stable placeholder: `<PERSON_1>`, `<AADHAAR_NUMBER_1>`, `<IN_PAN_2>`, etc.

`MaskingState` maintains a **bidirectional mapping**:
- `placeholder → original` (for restoration)
- `entity_type+original → placeholder` (for deduplication across turns)

### 9.4 Restoration

```python
restored_text = restore_text(masked_answer, masking_state)
```

Uses a **single compiled-regex pass** (`O(n)`) — the pattern `<([A-Z][A-Z0-9_]+_\d+)>` matches all placeholders and the `_replacer` looks them up in the mapping dict.

> ⚠️ **Important**: Assistant messages from history are **NOT re-masked**. They were already stored in PostgreSQL in restored form. Re-masking would cause the LLM to echo `<PERSON_1>` back to the user.

---

## 10. Memory Architecture

LawShield uses **three layers** of memory for contextual intelligence:

### 10.1 Sliding-Window Conversation Memory

```python
class SlidingWindowMemory:
    max_messages: int = 20  # configurable per session
```

- In-process dict keyed by `session_id`.
- When `len(messages) > max_messages`, the oldest non-system messages are dropped — the leading `SystemMessage` is always preserved.
- Rebuilt from PostgreSQL history on every request, ensuring consistency after server restarts.

### 10.2 Long-Term Fact Store (PostgreSQL)

After every completed exchange:

1. LLM is called with: *"Extract any long-term personal facts from this exchange as a JSON array."*
2. Facts saved to `LongTermFact` table (capped at 25 per thread).
3. On next request, injected into the system prompt:
   ```
   Long-term facts about this user:
   - User is a corporate lawyer specializing in M&A
   - User's client is a startup in Bangalore
   ```

**Why PostgreSQL?** Facts survive server restarts, support exact deduplication (`WHERE content = $1`), can be manually inspected, and cascade-delete with the thread.

### 10.3 Vector Memory (Qdrant)

After every exchange, the user+assistant pair is embedded (BGE-small-en-v1.5) and upserted to Qdrant's `conversation_history` collection with a `session_id` payload filter.

On each new request, `search_vector_memory(session_id, query, top_k=2)` retrieves the 2 most semantically similar past exchanges — injected into the system prompt as "Relevant past conversations." This lets Harvey reference context that has fallen out of the sliding window.

> ⚠️ Both memory writes happen as **background asyncio tasks** (fire-and-forget via `asyncio.to_thread`) so they never block the streaming response.

---

## 11. LLM Provider Layer

`llm/providers/factory.py` implements a **pluggable provider pattern**:

```python
get_llm_provider(provider_name: str | None) -> BaseLLMProvider
```

| Provider | Model | Temperature | Notes |
|---|---|---|---|
| `groq` (default) | `llama-3.1-8b-instant` | 0.2 | Ultra-fast inference |
| `openai` | `gpt-4o-mini` | 0.7 | High quality |
| `gemini` | `gemini-2.5-flash` | 0.7 | Google with thinking |
| `anthropic` | `claude-3-haiku-20240307` | 0.7 | Anthropic Haiku |

Every provider is wrapped in `RateLimitRetryWrapper`:
- Catches HTTP 429 / `rate_limit_exceeded` errors.
- Retries up to 3 times with **linear backoff**: 3s → 6s → 9s.
- Applies to both `.invoke()` (sync) and `.stream()` calls.

---

## 12. SSE Streaming Architecture

LawShield streams AI responses token-by-token using **Server-Sent Events (SSE)**.

**Event protocol:**
```
data: [Node: supervisor]\n\n    ← progress ping (agent pipeline step)
data: [Node: reasoning]\n\n     ← another step
data: [FINAL]\n\n               ← signals: next event is the full answer
data: The penalties under...\n\n ← the actual response text
data: [DONE]\n\n                 ← stream complete
```

**Python side** (`chat/router.py`):
- `StreamingResponse(event_generator(), media_type="text/event-stream")`
- `chat_service.stream_chat()` yields plain strings → router wraps each as `f"data: {chunk}\n\n"`
- On exception inside generator: yields `[FINAL]`, error message, `[DONE]` — never crashes silently.

**Node.js backend** (`routes/chat.js`):
- Sets SSE headers (`Content-Type: text/event-stream`, `X-Accel-Buffering: no`).
- Opens a raw `http.request` to Python — **not Axios** (Axios would buffer the whole response).
- Parses chunks, strips `data: ` prefix, re-emits to browser.
- On `[DONE]`: saves the assembled `finalAnswer` to PostgreSQL.

**Frontend** (`WorkspacePage.jsx`):
- Uses `fetch()` with `response.body.getReader()` to consume the stream.
- Splits on `\n\n` boundaries, strips `data: ` prefix.
- Live preview: `streamingContent` state updates on every chunk.
- On `[DONE]`: commits `finalText` as a permanent message, clears the live preview.

---

## 13. Observability Stack

### 13.1 Structured Logging

`observability/logs.py`:
- **JSON format** in production (`ENVIRONMENT=production`).
- **Human-readable** format in development.
- Log level controlled by `LOG_LEVEL` env var (default: `INFO`).
- Every module uses `logger = logging.getLogger(__name__)` — log lines carry the full module path.

### 13.2 OpenTelemetry Tracing

`observability/tracing.py`:
- Creates a `TracerProvider` with `service.name=lawshield-ai-service`.
- **Development**: `SimpleSpanProcessor` + `ConsoleSpanExporter` (spans printed to stdout).
- **Production**: `BatchSpanProcessor` + `OTLPSpanExporter` (Jaeger/Tempo/Datadog via gRPC when `OTEL_EXPORTER_OTLP_ENDPOINT` is set).
- **LangSmith**: if `LANGCHAIN_API_KEY` is set, enables `LANGCHAIN_TRACING_V2=true` for automatic LangChain trace capture.

The `trace_agent()` context manager wraps any agent node:
```python
with trace_agent("reasoning", session_id=session_id) as span:
    result = reasoning_agent.execute(state)
    span.set_attribute("confidence", str(result.confidence))
# On exception: records error on span, re-raises
```

### 13.3 Prometheus Metrics

Metrics exposed at `GET /metrics`:

| Metric | Type | Labels | Records |
|---|---|---|---|
| `http_requests_total` | Counter | method, endpoint, status | Every HTTP request |
| `http_request_duration_seconds` | Histogram | method, endpoint | Request latency |
| `llm_calls_total` | Counter | provider, model | LLM API calls |
| `llm_token_usage_total` | Gauge | provider, model, token_type | Token counts |
| `llm_latency_seconds` | Histogram | provider, model | LLM response time |
| `rag_search_duration_seconds` | Histogram | collection_name | Hybrid search latency |
| `agent_calls_total` | Counter | agent_name, status | Agent node executions |
| `agent_latency_seconds` | Histogram | agent_name | Per-agent timing |
| `legal_reasoning_confidence_score` | Gauge | session_id | Reasoning confidence |
| `reasoning_iterations_total` | Counter | result (clean/refined) | Self-correction count |

`ObservabilityMiddleware` automatically records HTTP metrics for every FastAPI request.

---

## 14. Database Schema

```sql
-- Users
User {
  id           UUID PRIMARY KEY
  name         TEXT
  email        TEXT UNIQUE
  passwordHash TEXT
  createdAt    TIMESTAMP
}

-- Conversation threads (one per chat session)
Thread {
  id        UUID PRIMARY KEY
  userId    UUID → User (cascade delete)
  title     TEXT
  createdAt TIMESTAMP
  updatedAt TIMESTAMP
}

-- Individual messages within a thread
Message {
  id        UUID PRIMARY KEY
  threadId  UUID → Thread (cascade delete)
  role      TEXT  -- "USER" | "ASSISTANT"
  content   TEXT
  sources   TEXT? -- JSON array e.g. '["Source A","Source B"]'
  createdAt TIMESTAMP
}

-- LLM-extracted long-term facts about the user
LongTermFact {
  id        UUID PRIMARY KEY
  threadId  UUID → Thread (cascade delete)
  content   TEXT
  createdAt TIMESTAMP
}

-- Uploaded document metadata (actual vectors live in Qdrant)
Document {
  id        UUID PRIMARY KEY
  userId    UUID → User (cascade delete)
  filename  TEXT
  fileType  TEXT
  size      TEXT  -- e.g. "2.34 MB"
  status    TEXT  -- "Ready" | "Processing" | "Processing Failed"
  createdAt TIMESTAMP
}
```

---

## 15. API Reference

### Backend (Node.js, port 3000)

**Auth**
```
POST /api/auth/register   { name, email, password }  →  { token, user }
POST /api/auth/login      { email, password }         →  { token, user }
```

**Threads**
```
GET    /api/threads                →  Thread[]
POST   /api/threads   { title }   →  Thread
GET    /api/threads/:id           →  Thread (with messages[])
DELETE /api/threads/:id           →  { msg }
```

**Chat**
```
POST /api/chat/         { threadId, message }   →  Message (full response)
POST /api/chat/stream   { threadId, message }   →  text/event-stream SSE
```

**Documents**
```
GET    /api/documents                              →  Document[]
POST   /api/documents/upload-and-ingest (multipart) →  { document, aiData }
DELETE /api/documents/:id                          →  { msg }
```

### AI Service (Python FastAPI, port 8000)

```
POST /chat/              { session_id, message, history?, provider? }  →  { response, sources }
POST /chat/stream        { session_id, message, history?, provider? }  →  text/event-stream SSE
POST /documents/upload-and-ingest  (multipart)  →  { status, chunks_indexed }
POST /rag/ingest         { text, metadata }      →  { status, chunks_indexed }
POST /rag/ask            { query, collection }   →  { answer, context_used }
GET  /health                                     →  { status: "healthy" }
GET  /metrics                                    →  Prometheus text format
GET  /docs                                       →  Swagger UI
```

---

## 16. Environment Variables

### `ai_service/.env`

```env
# LLM Provider API Keys
OPENAI_API_KEY=sk-...
GEMINI_API_KEY=AI...
ANTHROPIC_API_KEY=sk-ant-...
GROQ_API_KEY=gsk_...

# Default provider: openai | gemini | anthropic | groq
DEFAULT_LLM_PROVIDER=groq

# Databases
REDIS_URL=redis://localhost:6379
QDRANT_URL=http://localhost:6333
ELASTICSEARCH_URL=http://localhost:9200
DATABASE_URL=postgresql://user@localhost:5432/lawshield?schema=public

# Observability (optional)
LANGCHAIN_API_KEY=ls__...             # enables LangSmith tracing
OTEL_EXPORTER_OTLP_ENDPOINT=...      # enables OTLP export to Jaeger/Datadog
ENVIRONMENT=development               # or "production"
SERVICE_NAME=lawshield-ai-service
LOG_LEVEL=INFO
```

### `backend/.env`

```env
DATABASE_URL=postgresql://user@localhost:5432/lawshield?schema=public
JWT_SECRET=your_super_secret_key
AI_SERVICE_URL=http://127.0.0.1:8000
PORT=3000
```

### `frontend/.env`

```env
VITE_API_URL=http://localhost:3000/api
```

---

## 17. Running Locally

### Prerequisites

- Python 3.12 with `uv` or `pip`
- Node.js 20+
- PostgreSQL 15+
- Qdrant: `docker run -p 6333:6333 qdrant/qdrant`
- Elasticsearch 8 (optional — for hybrid BM25 search)

### Setup

```bash
# 1. Clone
git clone <repo-url> && cd lawShield

# 2. Backend
cd backend && npm install && cd ..

# 3. Prisma migrations
cd backend && npx prisma migrate deploy && cd ..

# 4. Frontend
cd frontend && npm install && cd ..

# 5. AI service
cd ai_service
python -m venv .venv && source .venv/bin/activate
pip install -e ".[all]"          # or: uv sync
python -m spacy download en_core_web_lg

# 6. Configure .env files (see section 16)
cp ai_service/.env.example ai_service/.env   # fill in API keys
cp backend/.env.example backend/.env

# 7. Start all services
cd .. && ./start.sh
```

**Services:**
- Frontend → http://localhost:5173
- Backend API → http://localhost:3000
- AI Service → http://localhost:8000
- Swagger UI → http://localhost:8000/docs

> ⚠️ **Port conflict warning**: If another Python service is running on port 8000 (e.g., a previous project), it will intercept all AI requests. Check with `lsof -i :8000` and kill stale processes before starting.

---

## 18. Interview Q&A — Deep Technical Questions

---

**Q: Why use LangGraph instead of a simple LangChain chain?**

LangGraph models the agent pipeline as a **directed state graph with conditional edges**, enabling:
- **Cycles**: the review node can reject a draft and loop back to the planner — impossible with a SequentialChain.
- **Parallel paths**: the supervisor routes to completely different subgraphs (research pipeline vs. direct contract analysis).
- **Persistent state**: every node reads from and writes to a shared `AgentState` TypedDict — no manual context threading.
- **Streaming**: `graph.astream()` yields intermediate states after each node, which we convert to SSE progress pings.

A LangChain `SequentialChain` only runs nodes in a fixed linear order.

---

**Q: How does PII masking work and why are assistant messages handled differently?**

User messages are masked using Presidio before any LLM sees them. The `MaskingState` stores `placeholder → original` mappings for the full conversation, and a combined state is built across all history turns so `<PERSON_1>` in turn 1 maps to the same person in turn 5.

Assistant messages from history are **not re-masked** because they were already stored in PostgreSQL in restored form. If we masked them again, the LLM would see `<PERSON_1>` in the conversation context and might echo the raw placeholder back in its answer, leaking it to the user. The masking is **one-way**: user data in → placeholder to LLM → real data in the final answer via `restore_text()`.

---

**Q: How do you prevent hallucinations in the RAG pipeline?**

Three layers:
1. **Hard refusal**: if `context_used` is empty (no relevant documents), a fixed refusal string is returned — no LLM call at all.
2. **Self-RAG evaluation**: after generating an answer, a grading LLM call checks whether the answer is supported by retrieved chunks. If not, the system regenerates using `_STRICT_REGEN_SYSTEM_PROMPT`: "every fact must be word-for-word from the context."
3. **Separated system prompts**: the RAG prompt, web-search prompt, and strict regen prompt are distinct and each explicitly forbids inventing statutes or case references.

---

**Q: Why Reciprocal Rank Fusion (RRF) for hybrid search instead of score fusion?**

RRF doesn't require score normalization. Qdrant returns cosine similarity scores in [−1, 1]; Elasticsearch BM25 scores are unbounded positive numbers. Combining them directly would require normalization, which is context-dependent and fragile. RRF only uses the **rank** of each document in each retriever's result list — a document ranked #1 in both retrievers scores higher than one ranked #1 in only one. The `k=60` smoothing constant prevents any single rank-1 result from dominating.

---

**Q: How is SSE different from WebSockets, and why did you choose SSE?**

SSE is **unidirectional** (server → client) over a single HTTP connection. WebSockets are bidirectional. Since chat streaming is strictly one-directional (server sends tokens; client sends new HTTP requests), SSE is simpler:
- No WebSocket handshake or keep-alive ping protocol needed.
- Works through standard HTTP proxies and load balancers without special config.
- Uses `fetch()` + `ReadableStream` for more control over aborting and error handling than the native `EventSource` API.

---

**Q: What happens if the AI service is down during a chat?**

The Node.js streaming proxy wraps everything in try/catch. On timeout or connection error, it emits:
```
data: [ERROR] An unexpected error occurred. Please try again.\n\n
data: [DONE]\n\n
```

The frontend's SSE parser catches `[ERROR]` and renders it as an assistant message. The user message is already saved to PostgreSQL (persisted before the AI call), so nothing is lost.

The non-streaming `/api/chat/` endpoint also has a fallback: if the AI service fails, the backend saves a graceful error message as the assistant response rather than returning a 500 to the user.

---

**Q: How does the sliding-window memory handle very long conversations?**

`SlidingWindowMemory` keeps up to 20 messages by default. When exceeded:
1. The leading `SystemMessage` (Harvey's full legal system prompt) is **always preserved**.
2. The oldest non-system messages (earliest user/assistant turns) are dropped.

The LLM always sees: system prompt + the most recent 19 messages.

For context pushed out of the window, the **vector memory** layer (Qdrant) surfaces relevant past exchanges semantically when they're topically related to the new query — so Harvey can still recall key facts from earlier in long conversations.

---

**Q: Why PostgreSQL for long-term facts instead of keeping everything in Qdrant?**

Long-term facts are **structured, discrete strings** — not embeddings. PostgreSQL enables:
- **Exact deduplication**: `WHERE content = $1` prevents the same fact from being inserted twice.
- **Per-session capping**: delete oldest N rows when count exceeds 25.
- **Manual inspection and editing**: facts can be directly queried and modified for debugging.
- **Cascade deletes**: when a thread is deleted, all its facts are automatically removed.

Qdrant is purpose-built for **vector similarity search** — not for structured row queries or exact deduplication. Using the right database for each data type is a core architectural principle here.

---

**Q: How do you ensure the system is testable despite all the dependencies?**

- `ChatService` accepts an optional `provider_name` parameter — tests can inject a mock/stub provider.
- `MaskingState` is a pure Python class with zero external dependencies — fully unit-testable.
- `mask_and_restore_passthrough(text)` is a built-in round-trip test helper.
- The LangGraph graph is compiled once (`create_graph()`) and can be invoked with a constructed `AgentState` dict, bypassing all real LLM calls if mocked.
- The observability layer uses standard Python `logging` — captured with `pytest`'s `caplog` fixture.
- All background memory tasks (`asyncio.to_thread(...)`) are swallowed individually so a failure in fact extraction never breaks the primary response path.

---

*Built with ❤️ for Indian legal professionals.*
*Harvey knows the IPC, Constitution, and Supreme Court — so you don't have to memorize everything.*
