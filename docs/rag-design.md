# RAG Strategy Design

## Pipeline Overview

```text
Document Upload → Parse → Chunk → Embed → Store
                                 ↓
User Question → Rewrite → Multi-Query → Hybrid Retrieve → Rerank → Prompt → Generate → Cite
```

## 1. Document Ingestion

### Supported Formats
- PDF: via `pypdf` + `unstructured`
- Markdown: native parsing with header-aware splitting
- TXT: line-based splitting
- DOCX: via `python-docx` + `unstructured`

### Chunking Strategy
- **Default**: RecursiveCharacterTextSplitter (chunk_size=1000, overlap=200)
- **Semantic**: Split on natural boundaries (paragraphs, sections) when possible
- **Metadata**: Each chunk carries `{doc_id, doc_title, page, chunk_index, department, access_level}`

### Embedding
- **Model**: `text-embedding-3-small` (1536d), upgradeable to `text-embedding-3-large` (3072d)
- **Batching**: 100 chunks per API call
- **Retry**: Exponential backoff with 3 retries

## 2. Retrieval

### Hybrid Search Architecture
```text
Query ──┬── Dense Retrieval (pgvector cosine similarity) ──┐
        │                                                   ├── Fusion (RRF) ── Reranker ── Top K
        └── Sparse Retrieval (BM25 via pg_trgm / ES) ──────┘
```

### Dense Retrieval
- `pgvector` HNSW index for approximate nearest neighbor search
- Cosine similarity as default distance metric
- Metadata pre-filtering for RBAC (department, access_level)

### Sparse Retrieval (BM25)
- Stage 1: PostgreSQL full-text search (`tsvector` / `tsquery`) with `pg_trgm`
- Stage 2 (optional): Elasticsearch for production-scale BM25

### Fusion
- **RRF (Reciprocal Rank Fusion)**: Combines dense and sparse result lists
- Formula: `RRF(d) = Σ 1/(k + rank_i(d))`

### Reranker
- **Provider options**: Cohere Rerank, BGE Reranker-v2-m3, Jina Reranker
- **Default**: Cohere Rerank v3
- **Process**: Recall ~30 candidates → Rerank → Return Top 5
- **Fallback**: Local `BAAI/bge-reranker-v2-m3` via `sentence-transformers`

## 3. Query Processing

### Query Rewrite
- Use LLM to expand abbreviations, add context, normalize phrasing
- Example: "年假怎么请?" → "公司员工年假请假流程和规定是什么?"

### Multi-Query Retrieval
- Generate 2-3 sub-queries from the original question
- Retrieve for each sub-query independently
- Merge and deduplicate results

## 4. Prompt Engineering

### System Prompt Template
```text
你是一个企业知识库助手。请仅根据以下提供的文档片段回答用户的问题。
如果文档中没有相关信息，请如实告知"根据现有文档无法确认"，不要编造内容。

回答要求：
1. 引用具体的文档来源（文档名称、章节）
2. 如果涉及流程，按步骤列出
3. 如果信息不完整，指出缺失的部分
4. 使用中文回答

参考文档：
---
{context}
---
```

### Citation
- Each chunk carries metadata: `{doc_title, page, chunk_id, department}`
- Answer text embeds citation markers: `[1]`, `[2]`
- Response includes a `sources` array with full metadata per marker

## 5. RBAC Filtering

Documents and chunks carry `access_level` and `allowed_departments` metadata. During retrieval:
1. Pre-filter by user's department: `metadata.department IN user.departments`
2. Post-filter by access level: `metadata.access_level <= user.clearance_level`
3. This filtering happens at the vector store query level (not post-hoc)
