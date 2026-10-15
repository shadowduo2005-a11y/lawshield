# LawShield RAG Architecture & Workflow Graph

This document provides a comprehensive visual representation and architecture breakdown of the **Self-RAG (Adaptive Hybrid Retrieval-Augmented Generation)** system built into LawShield.

---

## 1. End-to-End RAG Architecture Diagram

```mermaid
flowchart TD
    %% Styling
    classDef input fill:#e1f5fe,stroke:#0288d1,stroke-width:2px,color:#01579b;
    classDef router fill:#fff3e0,stroke:#f57c00,stroke-width:2px,color:#e65100;
    classDef ingest fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px,color:#4a148c;
    classDef process fill:#e8f5e9,stroke:#388e3c,stroke-width:2px,color:#1b5e20;
    classDef eval fill:#fce4ec,stroke:#c2185b,stroke-width:2px,color:#880e4f;
    classDef output fill:#e0f2f1,stroke:#00796b,stroke-width:2px,color:#004d40;
    classDef refusal fill:#ffebee,stroke:#d32f2f,stroke-width:2px,color:#b71c1c;

    %% Ingestion Flow
    subgraph Ingestion ["1. Document Ingestion Pipeline"]
        DocInput["Legal Document / PDF"] ::: input
        Chunker["Recursive Text Chunker & Metadata Tagger"] ::: ingest
        Embedder["BGE / Dense Embedding Model"] ::: ingest
        Qdrant[("Qdrant Vector DB (Semantic Index)")] ::: ingest
        ES[("Elasticsearch DB (Lexical Index)")] ::: ingest

        DocInput --> Chunker
        Chunker --> Embedder
        Embedder --> Qdrant
        Chunker --> ES
    end

    %% Query & Routing Flow
    subgraph QueryRouting ["2. Adaptive Query Routing"]
        UserQuery["User Query"] ::: input
        Supervisor["Supervisor Router Agent"] ::: router

        UserQuery --> Supervisor
        Supervisor -->|"Pure Greetings / Small Talk"| DirectLLM["Direct Friendly LLM Response"] ::: output
        Supervisor -->|"Live News / Current Acts"| WebSearch["Web Search Engine (Tavily/DDG)"] ::: process
        Supervisor -->|"Document Query / Contract / Statutory Law"| SelfRAGLoop["Self-RAG Engine"] ::: router
    end

    %% Self-RAG Reflection Loop Flow
    subgraph RetrievalEngine ["3. Self-RAG Retrieval & Reflection Loop"]
        SelfRAGLoop --> QueryRewrite["Query Rewriter Node"] ::: process
        QueryRewrite --> MetaFilter["Metadata Filter Extractor"] ::: process

        MetaFilter --> HybridSearch["Advanced Hybrid Search (Vector + Lexical RRF Fusion)"] ::: process
        Qdrant -.-> HybridSearch
        ES -.-> HybridSearch

        HybridSearch --> Reranker["Cross-Encoder Reranker (Top K Documents)"] ::: process
        Reranker --> IsRel{"IsRel Check: Grade Document Relevance"} ::: eval

        IsRel -->|"Relevant Chunks Found"| Generator["Grounded LLM Generator"] ::: process
        IsRel -->|"No Relevant Chunks"| RetryQuery["Broaden Query & Retry (Attempt < 3)"] ::: refusal
        RetryQuery --> QueryRewrite

        Generator --> IsSup{"IsSup Check: Hallucination Check"} ::: eval

        IsSup -->|"Hallucinated / Unsupported Claims"| StrictRegen["Strict Regeneration Prompt (Word-for-Word Context)"] ::: eval
        StrictRegen --> ReCheckSup{"Re-check Grounding"} ::: eval
        ReCheckSup -->|"Passes"| IsUse{"IsUse Check: Answer Relevance"} ::: eval
        ReCheckSup -->|"Fails Again"| RetryQuery

        IsSup -->|"Grounded in Context"| IsUse

        IsUse -->|"Answers Query"| CitationGen["Citation Generator (Bluebook & Indian Courts)"] ::: process
        IsUse -->|"Off-topic / Unhelpful"| RetryQuery
    end

    %% Output Node
    CitationGen --> FinalAnswer["Final Verified Answer + Citations"] ::: output
    WebSearch --> WebPrompt["Web Summary Prompt (Strict Anti-Hallucination)"] ::: process
    WebPrompt --> FinalAnswer

    RetryQuery -->|"Retries Exhausted (Attempt >= 3)"| HardRefusal["Hard Refusal Response"] ::: refusal
```

---

## 2. RAG System Components Overview

| Component | Module Location | Function & Purpose |
| :--- | :--- | :--- |
| **Document Ingestor** | `rag/pipelines.py`, `rag/chunking.py` | Chunks legal documents and dual-indexes them into vector (Qdrant) and lexical (Elasticsearch) databases. |
| **Adaptive Router** | `agents/supervisor/agent.py`, `rag/adaptive/router.py` | Classifies incoming query intent (`FINISH` for greetings, `web_search` for current news, `rag`/`qa` for document/legal queries). |
| **Query Rewriter** | `rag/adaptive/query_rewrite.py` | Optimizes and expands legal queries for better retrieval precision. |
| **Metadata Filter** | `rag/metadata/filters.py` | Extracts metadata constraints (years, jurisdiction, statute types) to narrow search scope. |
| **Hybrid Search** | `rag/hybrid/search.py` | Merges Qdrant vector semantic search with Elasticsearch lexical search using Reciprocal Rank Fusion (RRF). |
| **Reranker** | `rag/reranker.py` | Scores candidate chunks using a cross-encoder model to surface the top 5 most relevant passages. |
| **Self-RAG Evaluators** | `rag/self_rag/evaluator.py` | **IsRel**: Grades document relevance.<br>**IsSup**: Checks for hallucinations.<br>**IsUse**: Verifies answer utility. |
| **Citation Generator** | `rag/citation/generator.py` | Injects precise Indian court and statute citations into the final answer. |

---

## 3. Anti-Hallucination Safeguards

1. **Dual Indexing & Hybrid RRF**: Combines keyword precision (lexical) with deep context understanding (vector).
2. **Self-Correction Reflection Loop**: Automatically rewrites failed queries and retries up to 3 times.
3. **Strict Regeneration Fallback**: If an initial response contains unsupported claims, the engine forces word-for-word context generation.
4. **Hard Refusal Guarantee**: If grounding cannot be established after 3 attempts, the pipeline returns a clean refusal rather than fabricating information.
