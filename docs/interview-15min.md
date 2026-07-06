# 15-Minute Deep-Dive Interview Guide

## 1. Project Motivation & Problem Statement (2 min)

**面试官可能会问："为什么做这个项目？解决什么问题？"**

回答要点：
- 企业有大量散落在各处的文档（制度、手册、FAQ、合同），员工查找效率低
- 通用 AI（ChatGPT）不能访问企业内部数据，且无法溯源
- 需要一个可控、可审计、基于企业自有知识库的问答系统
- RAG 是当前业界验证过的最有效方案（比微调成本低、可解释性强）

---

## 2. Architecture Deep Dive (4 min)

**Q: "为什么选 LangGraph 而不是直接用 LangChain Chain？"**

- LangGraph 是状态机模型，适合有分支、循环、条件判断的 Agent 流程
- 支持 durable execution：Agent 运行中出错可以恢复，不像 Chain 要从头开始
- 原生 human-in-the-loop：高风险答案可以插入人工审核节点，审核通过再返回给用户
- 支持 persistence：可以把对话状态持久化到数据库，支持对话恢复
- 支持 streaming：每个节点的输出都可以流式返回给前端

**Q: "为什么选 pgvector 而不是直接用 Milvus/Qdrant/Chroma？"**

- pgvector 在 PostgreSQL 内部运行，向量和业务数据在同一张表，JOIN 查询方便
- 企业通常已经有 PostgreSQL，加装 pgvector 扩展即可，运维成本低
- 适合百万级向量场景（中小企业知识库）
- 架构上预留了 Milvus 接口，向量量大了可以无缝切换
- pgvector 支持 HNSW、IVFFlat、cosine/L2/inner product

**Q: "FastAPI vs Flask/Django？"**

- FastAPI 原生异步（asyncio），RAG 场景大量 I/O（API 调用、DB 查询），异步收益大
- 自动生成 OpenAPI 3.0 文档（Swagger），对接前端友好
- Pydantic v2 类型校验，请求参数和响应格式自动验证
- 支持 SSE streaming，SSE 比 WebSocket 更轻量，适合问答这种单向流场景

---

## 3. RAG Pipeline Deep Dive (4 min)

**Q: "你的检索策略具体怎么做的？"**

```
用户问题 → Query Rewrite（LLM改写） → Multi-Query（生成子问题）
    → Dense Retrieval（向量语义匹配,T=30）
    + Sparse Retrieval（BM25关键词匹配,T=30）
    → RRF Fusion（Reciprocal Rank Fusion合并去重）
    → Reranker（Cohere/BGE重排到Top 5）
    → Context Assembly + Citation
    → LLM生成
```

**Q: "为什么要用 Hybrid Search？纯向量检索不够吗？"**

- 向量检索擅长语义匹配但不擅长精确关键词（比如 "API v3.2" "合同编号 CON-2024-001"）
- BM25 关键词检索互补——精确匹配编号、术语、版本号
- 两者融合后召回率通常能提升 10-20%
- RRF (Reciprocal Rank Fusion) 是一种简单有效的融合算法：`RRF(d) = Σ 1/(60 + rank_i(d))`

**Q: "Reranker 为什么重要？"**

- 向量检索召回 30 条，靠 cosine similarity 排序不够精确
- Reranker 是 Cross-Encoder，输入 (query, doc) pair 做深度语义匹配
- 相当于一个精排模型，把 Top 30 重排为 Top 5
- 经验数据：Reranker 能让最终答案的事实准确性提升 15-25%
- 支持多个 Provider（Cohere/云端、BGE/本地部署），能根据延迟和成本权衡

**Q: "引用溯源怎么做的？"**

- 每个 chunk 在入库时携带 metadata：`{doc_id, doc_title, page_number, chunk_index, department, version}`
- LLM 生成答案时要求标注引用位置 `[1]` `[2]`
- 返回的 `sources` 数组包含完整的溯源信息
- 用户点击引用可以看到原文片段

---

## 4. Agent Design (2 min)

**Q: "LangGraph Agent 的状态机怎么设计的？"**

```text
START → classify_question
    ├── policy_qa → retrieve_docs → generate → END
    ├── data_query → query_sql → generate → END
    ├── comparison → retrieve_docs × 2 → compare → generate → END
    ├── summarization → retrieve_doc → summarize → END
    └── unknown → ask_clarification → END
```

- Classify Node: 用 LLM 判断问题类型 + 是否需要工具调用
- Retrieve Node: 调用 Hybrid Retrieval
- Generate Node: 组装 prompt + 调用 LLM + 格式化引用
- Tool Node: 执行工具调用（SQL 查询/文档对比/创建工单）
- Fallback: 检索置信度低于阈值时追问用户或返回"无法确认"

**Q: "Human-in-the-loop 怎么实现的？"**

- 在 LangGraph 中设置 `interrupt_before=["generate"]`
- 高风险场景（比如法律合规问题）会中断流程
- 管理员在前端审核检索结果和生成的答案
- 审核通过 → 继续执行 → 返回用户
- 审核拒绝 → 重新检索或标记为需要人工回答

---

## 5. Evaluation & Observability (2 min)

**Q: "你怎么评估 RAG 系统好坏？"**

检索指标（离线）：
- Hit Rate@K：相关文档在 Top K 中的命中率
- MRR：第一个相关文档的平均排名倒数
- Recall@K：所有相关文档中被检索到的比例

生成指标（用 Ragas）：
- Faithfulness：生成的内容是否都能在上下文中找到依据（最重要！）
- Answer Relevance：回答是否切题
- Context Precision：检索到的上下文中有多少是相关的
- Context Recall：应该检索到的信息实际检索到了多少

生产监控：
- LangSmith 追踪每次 Agent 调用链（retrieve → rerank → generate → tool calls）
- Prometheus + Grafana 监控延迟、QPS、错误率、Token 用量和成本
- 用户反馈收集（👍/👎）→ 自动加入 Golden Dataset 扩展

---

## 6. Challenges & Trade-offs (1 min)

**Q: "做这个项目最大的技术挑战是什么？"**

1. **分块策略**：太大的 chunk 包含噪声，太小的 chunk 丢失上下文。最终选择了语义分块（按自然段落）+ 滑动窗口重叠。
2. **中英混合检索**：中文语义检索和英文关键词检索的融合，BM25 对中文分词不太友好，引入了 jieba 分词。
3. **幻觉控制**：即使有 RAG，LLM 偶尔也会编造。通过 strict prompt + 低 temperature + Faithfulness 指标兜底。
4. **成本和质量平衡**：每次查询可能调用多次 LLM（Rewrite + Multi-Query + Generate），做了缓存层和 fallback 链（大模型失败时降级到小模型）。
