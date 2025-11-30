# Lab 3 — Advanced RAG with Azure AI Search × Copilot Studio

## Objectives
1. Design and build an Azure AI Search index optimized for RAG.
2. Implement ingestion, chunking, vectorization, semantic ranking, and scoring profiles.
3. Explore hybrid and semantic queries, filters, and evaluation metrics.
4. Integrate the index with a Copilot Studio agent using:
   - Knowledge Source (quick setup)
   - HTTP connector (full control)
   - Real-time knowledge connectors
5. Orchestrate a controlled RAG pipeline in Copilot Studio with tools and prompts.

---

## Part 1 — Prepare Azure AI Search

### 1.1 Index Design
- Create fields: `chunk_text`, `chunk_vector`, `source_url`, `tags`, `locale`.
- Enable vector search and semantic ranker.
- Define scoring profiles for business signals if needed.

### 1.2 Data Ingestion
- Use Indexers + Skillsets for OCR, layout extraction, and chunking.
- Configure integrated or external vectorization.
- Validate index schema and test queries in the portal.

---

## Part 2 — Query Patterns
- **Vector query**: POST with `vectorQueries` specifying embedding and k.
- **Hybrid query**: Combine `search` (BM25) + `vectorQueries` with RRF.
- **Semantic ranker**: Enable for improved relevance and captions.
- Apply filters and select minimal fields to reduce payload size.

---

## Part 3 — Integration with Copilot Studio

### Option A: Knowledge Source
- Add Azure AI Search as a knowledge source in the agent.
- Pros: Quick setup. Cons: Limited query control.

### Option B: HTTP Connector
- Create a custom connector or Power Automate flow calling the Search REST API.
- Inputs: `user_query`, `embedding`, `filters`.
- Outputs: `chunk_text`, `source_url`.
- Map as a Tool in the agent and orchestrate via instructions.

### Option C: Real-time Connectors
- Use real-time knowledge connectors for federated queries without data duplication.

---

## Part 4 — Agent Orchestration
- Add Tool `searchRag` (HTTP connector).
- Add Prompt Tool for post-processing (tone, PII checks, summarization).
- Instructions: When user asks domain-specific questions, call `searchRag`, then summarize with citations.

---

## Best Practices
- Use hybrid + semantic ranker for better recall and precision.
- Chunk size: 800–1200 tokens with overlap.
- Monitor payload size (Copilot Studio connector limit ~450 KB).
- Secure endpoints with Private Link or Managed Identity.

---

## Validation
- Test queries with and without filters.
- Evaluate retrieval quality using NDCG, XDCG, Fidelity.
- Measure latency and user satisfaction.

---

## Cleanup
- Remove Copilot Studio agent and connectors.
- Delete AI Search index and resources to avoid costs.

---
