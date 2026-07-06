# 5-Minute Interview Walkthrough

## Project: Enterprise Knowledge RAG Agent

### Opening (30s)
"我做了一个企业级知识库检索与问答系统，类似于企业内部的 ChatGPT，但它只会基于企业自己的文档回答，并且能追踪每句话的来源。技术栈是 FastAPI + LangGraph + pgvector + Next.js。"

---

### Architecture (1 min)
"系统分为六层：
- **前端** Next.js，支持流式聊天和文档管理后台
- **API 层** FastAPI，异步非阻塞，自动生成 Swagger 文档
- **Agent 层** LangGraph 编排，能根据问题类型自动路由——比如制度类问题走文档检索，数据查询走 SQL
- **RAG 层** 混合检索：语义检索 + 关键词检索 + Reranker 重排，保证召回率和准确率
- **数据层** PostgreSQL + pgvector 向量存储 + Redis 缓存 + MinIO 文件存储
- **可观测层** LangSmith 追踪 + Prometheus + Grafana 监控 + Ragas 自动评估"

---

### Technical Highlights (2 min)
**1. 检索质量：** "RAG 最大的难点不是调 API，而是检索质量。我做了三层优化：
- Hybrid Search：dense semantic + BM25 sparse，用 RRF 融合
- Reranker：先用向量检索召回 30 条，再用 Cohere/BGE Reranker 重排到 Top 5
- Query Rewrite：把用户的模糊问题改写成精确的检索查询"

**2. Agent 能力：**
"用 LangGraph 实现了问题分类 → 条件路由 → 工具调用 → 多步推理。支持 search_docs、query_sql、summarize、compare 等工具。检索不到时会主动追问用户或返回无法确认，不会瞎编。"

**3. 企业级特性：**
"实现了 JWT + RBAC 权限隔离，HR 文档、财务文档、技术文档按角色过滤；文档版本管理；异步任务队列处理大文件解析和 embedding；全链路审计日志。"

**4. 评估体系：**
"准备了 50-100 条标准问答对做 Golden Dataset，用 Ragas 跑 Hit Rate@K、MRR、Faithfulness、Answer Relevance 等指标，每次 PR 都会自动评估，指标退化超过 5% 会阻塞合并。"

---

### Demo Flow (1 min)
"给你演示一下：
1. 上传一份公司制度 PDF
2. 问 '年假怎么请？'——系统检索相关片段，返回带引用的答案
3. 问 '对比一下员工手册和劳动合同里的试用期规定'——Agent 会调用 compare 工具，分别检索两个文档然后综合对比
4. 后台可以看到这次查询命中了哪些文档、延迟多少、花了多少 token"

---

### Results & Learnings (30s)
"这个项目让我深入理解了 RAG 系统的核心挑战：不在于调用大模型 API，而在于端到端的工程链路——文档解析质量、分块策略、检索召回、重排序、引用可信度、评估反馈闭环。也让我的系统设计能力从 '写代码' 提升到 '构建可运维、可评估、可进化的 AI 应用'。"
