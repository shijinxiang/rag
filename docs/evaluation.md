# RAG Evaluation Framework

## Metrics Overview

We evaluate RAG systems on two dimensions: **retrieval quality** and **generation quality**.

### Retrieval Metrics

| Metric | Formula | Target |
|---|---|---|
| Hit Rate@K | `|relevant ∩ retrieved@K| / |relevant|` | > 0.85 |
| MRR (Mean Reciprocal Rank) | `1/|Q| Σ 1/rank_i` | > 0.70 |
| Recall@K | `|relevant ∩ retrieved@K| / |relevant|` | > 0.90 |
| Precision@K | `|relevant ∩ retrieved@K| / K` | > 0.50 |

### Generation Metrics (via Ragas)

| Metric | Description | Target |
|---|---|---|
| Faithfulness | Are claims grounded in context? | > 0.85 |
| Answer Relevance | Does the answer address the question? | > 0.80 |
| Context Precision | Are retrieved chunks relevant? | > 0.80 |
| Context Recall | Is all relevant info retrieved? | > 0.85 |

### Production Metrics

| Metric | Description |
|---|---|
| Latency (P50/P95/P99) | Time from question to answer |
| Token Usage | Input + output tokens per query |
| Cost | USD per query, per day |
| Error Rate | Failed retrievals / generations |
| Feedback Ratio | 👍 / (👍 + 👎) |

## Golden Dataset

A curated set of 50-100 Q&A pairs covering all document types:

```json
{
  "id": "qa-001",
  "question": "公司年假申请流程是什么？",
  "expected_answer": "员工需提前3个工作日...",
  "relevant_docs": ["doc-hr-policy-2024"],
  "relevant_chunks": ["chunk-001", "chunk-002"],
  "category": "hr_policy",
  "difficulty": "easy"
}
```

### Dataset Categories
- **hr_policy**: Leave, benefits, code of conduct
- **product_doc**: Product specs, API docs, user manuals
- **faq**: Common questions and answers
- **legal**: Contracts, NDAs, compliance
- **tech_manual**: Technical procedures, runbooks

## Running Evaluation

```bash
# Run full evaluation suite
python scripts/run_evaluation.py \
  --dataset data/golden_dataset/qa_pairs.json \
  --metrics all \
  --output results/eval_$(date +%Y%m%d).json

# Run specific metrics
python scripts/run_evaluation.py \
  --dataset data/golden_dataset/qa_pairs.json \
  --metrics hit_rate,mrr,faithfulness

# Compare two runs
python scripts/run_evaluation.py \
  --compare results/eval_before.json results/eval_after.json
```

## Evaluation CI Pipeline

Evaluations run in CI on every PR:
1. Run Ragas evaluation on Golden Dataset
2. Compare metrics against baseline
3. Block merge if metrics degrade > 5%

## Feedback Loop

User feedback (👍/👎) is collected and used to:
1. Identify poor-performing queries
2. Add corrected Q&A pairs to Golden Dataset
3. Fine-tune retrieval parameters
4. Update prompt templates
