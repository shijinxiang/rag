"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  FiCheck,
  FiClipboard,
  FiClock,
  FiRefreshCw,
  FiSearch,
  FiShield,
  FiX,
} from "react-icons/fi";
import {
  audits,
  decideReview,
  reviews,
  type Audit,
  type Review,
} from "@/lib/api";
import {
  ConfirmDialog,
  EmptyState,
  errorMessage,
  formatDate,
  IconButton,
  StatusBadge,
} from "@/components/ui";

const actionNames: Record<string, string> = {
  "document.delete": "删除文档",
  "document.reprocess": "重新处理文档",
  "document.upload": "上传文档",
  "document.retry": "重试处理",
  "document.queue_failed": "任务入队失败",
  "review.request": "提交审核",
  "review.approved": "批准审核",
  "review.rejected": "拒绝审核",
};

export default function Administration() {
  const [reviewList, setReviewList] = useState<Review[]>([]);
  const [auditList, setAuditList] = useState<Audit[]>([]);
  const [error, setError] = useState("");
  const [decisionError, setDecisionError] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [search, setSearch] = useState("");
  const [outcome, setOutcome] = useState("");
  const [decision, setDecision] = useState<{
    review: Review;
    action: "approve" | "reject";
  } | null>(null);
  const requestId = useRef(0);
  const load = useCallback(async () => {
    const id = ++requestId.current;
    try {
      const [nextReviews, nextAudits] = await Promise.all([
        reviews(),
        audits(),
      ]);
      if (requestId.current === id) {
        setReviewList(nextReviews);
        setAuditList(nextAudits);
        setError("");
      }
    } catch (cause) {
      if (requestId.current === id) setError(errorMessage(cause));
    } finally {
      if (requestId.current === id) setLoading(false);
    }
  }, []);
  const invalidate = useCallback(() => {
    requestId.current++;
  }, []);
  useEffect(() => {
    void load();
    const timer = setInterval(load, 10000);
    return () => {
      clearInterval(timer);
      invalidate();
    };
  }, [load, invalidate]);
  async function submitDecision() {
    if (!decision || busy) return;
    setBusy(true);
    setDecisionError("");
    setMessage("");
    try {
      await decideReview(decision.review.id, decision.action);
      setMessage(decision.action === "approve" ? "审核已批准" : "审核已拒绝");
      setDecision(null);
      await load();
    } catch (cause) {
      setDecisionError(errorMessage(cause));
    } finally {
      setBusy(false);
    }
  }
  const visible = auditList.filter(
    (item) =>
      (!outcome || item.outcome === outcome) &&
      `${item.action} ${actionNames[item.action] || ""} ${item.resource_id || ""}`
        .toLowerCase()
        .includes(search.trim().toLowerCase()),
  );
  return (
    <section className="data-page">
      <div className="page-heading">
        <div>
          <span className="eyebrow">GOVERNANCE</span>
          <h1>审核与审计</h1>
          <p>企业全部部门</p>
        </div>
        <IconButton
          label="刷新审核与日志"
          disabled={loading || busy}
          onClick={() => {
            setLoading(true);
            void load();
          }}
        >
          <FiRefreshCw className={loading ? "spin" : ""} />
        </IconButton>
      </div>
      {error && (
        <div className="notice error" role="alert">
          {error}
        </div>
      )}
      {decisionError && !decision && (
        <div className="notice error" role="alert">
          {decisionError}
        </div>
      )}
      {message && (
        <div className="notice success" role="status">
          {message}
        </div>
      )}
      <section className="admin-section">
        <div className="section-heading">
          <h2>
            <FiShield />
            待审核<span className="count-badge">{reviewList.length}</span>
          </h2>
          <span className="section-meta">
            <FiClock />
            {loading ? "更新中" : "待处理请求"}
          </span>
        </div>
        {reviewList.map((item) => (
          <div className="review-row" key={item.id}>
            <span className="review-symbol" aria-hidden="true">
              <FiClipboard />
            </span>
            <div className="review-detail">
              <strong>{actionNames[item.action] || item.action}</strong>
              <span>
                {item.payload.document_title ||
                  item.payload.document_id ||
                  item.id}
              </span>
              {item.created_at && <time>{formatDate(item.created_at)}</time>}
            </div>
            <div className="review-actions">
              <button
                className="button secondary"
                disabled={busy}
                onClick={() => {
                  setDecisionError("");
                  setDecision({ review: item, action: "reject" });
                }}
              >
                <FiX />
                拒绝
              </button>
              <button
                className="button primary"
                disabled={busy}
                onClick={() => {
                  setDecisionError("");
                  setDecision({ review: item, action: "approve" });
                }}
              >
                <FiCheck />
                批准
              </button>
            </div>
          </div>
        ))}
        {!reviewList.length && (
          <EmptyState
            icon={<FiCheck />}
            title={loading ? "正在加载审核请求" : "暂无待审核请求"}
          />
        )}
      </section>
      <section className="admin-section">
        <div className="section-heading">
          <h2>
            <FiClock />
            审计日志
          </h2>
          <span className="section-meta">最近 {auditList.length} 条</span>
        </div>
        <div className="document-toolbar">
          <label className="search-field">
            <FiSearch />
            <input
              aria-label="搜索审计日志"
              placeholder="搜索动作或资源"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </label>
          <label className="filter-field">
            <select
              aria-label="审计结果"
              value={outcome}
              onChange={(event) => setOutcome(event.target.value)}
            >
              <option value="">全部结果</option>
              <option value="success">成功</option>
              <option value="error">失败</option>
            </select>
          </label>
        </div>
        <div className="table-scroll">
          <table className="data-table audit-table">
            <thead>
              <tr>
                <th>时间</th>
                <th>动作</th>
                <th>资源</th>
                <th>结果</th>
              </tr>
            </thead>
            <tbody>
              {visible.map((item) => (
                <tr key={item.id}>
                  <td>
                    <time>{formatDate(item.created_at)}</time>
                  </td>
                  <td>{actionNames[item.action] || item.action}</td>
                  <td className="resource-id">{item.resource_id || "—"}</td>
                  <td>
                    <StatusBadge
                      status={item.outcome}
                      label={item.outcome === "error" ? "失败" : undefined}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {!visible.length && (
          <EmptyState
            icon={<FiClock />}
            title={loading ? "正在加载日志" : "暂无匹配日志"}
          />
        )}
      </section>
      {decision && (
        <ConfirmDialog
          title={decision.action === "approve" ? "批准审核" : "拒绝审核"}
          description={`${decision.action === "approve" ? "确认批准" : "确认拒绝"}这项${actionNames[decision.review.action] || decision.review.action}请求？`}
          confirmLabel={decision.action === "approve" ? "批准" : "拒绝"}
          busy={busy}
          error={decisionError}
          onClose={() => setDecision(null)}
          onConfirm={() => void submitDecision()}
        />
      )}
    </section>
  );
}
