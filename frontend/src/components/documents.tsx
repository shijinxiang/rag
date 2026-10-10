"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  FiChevronLeft,
  FiChevronRight,
  FiFileText,
  FiFilter,
  FiRefreshCw,
  FiSearch,
  FiTrash2,
  FiUpload,
  FiX,
} from "react-icons/fi";
import {
  deleteDocument,
  documentAction,
  listDocuments,
  uploadDocument,
  type DocumentInfo,
  type DocumentList,
  type UserInfo,
} from "@/lib/api";
import {
  ConfirmDialog,
  EmptyState,
  errorMessage,
  formatDate,
  IconButton,
  StatusBadge,
} from "@/components/ui";

function formatSize(bytes: number) {
  return bytes < 1024 * 1024
    ? `${Math.max(1, Math.round(bytes / 1024))} KB`
    : `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export default function Documents({ user }: { user: UserInfo }) {
  const [data, setData] = useState<DocumentList | null>(null);
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState("");
  const [search, setSearch] = useState("");
  const [uploadDepartment, setUploadDepartment] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [actionError, setActionError] = useState("");
  const [message, setMessage] = useState("");
  const [deleting, setDeleting] = useState<DocumentInfo | null>(null);
  const requestId = useRef(0);
  const uploadInput = useRef<HTMLInputElement>(null);
  const load = useCallback(async () => {
    const id = ++requestId.current;
    try {
      const next = await listDocuments(
        page,
        20,
        undefined,
        status || undefined,
      );
      if (requestId.current !== id) return;
      if (page > next.pages) {
        setPage(next.pages);
        return;
      }
      setData(next);
      setError("");
    } catch (cause) {
      if (requestId.current === id) setError(errorMessage(cause));
    } finally {
      if (requestId.current === id) setLoading(false);
    }
  }, [page, status]);
  const invalidate = useCallback(() => {
    requestId.current++;
  }, []);
  useEffect(() => {
    setLoading(true);
    void load();
    const timer = setInterval(load, 5000);
    return () => {
      clearInterval(timer);
      invalidate();
    };
  }, [load, invalidate]);
  async function action(fn: () => Promise<unknown>, success: string) {
    if (busy) return;
    setBusy(true);
    setActionError("");
    setMessage("");
    try {
      await fn();
      setMessage(success);
      await load();
    } catch (cause) {
      setActionError(errorMessage(cause));
    } finally {
      setBusy(false);
    }
  }
  const visible = (data?.items || []).filter((doc) =>
    doc.title.toLowerCase().includes(search.trim().toLowerCase()),
  );
  const pageCount = data?.pages || 1;
  return (
    <section className="data-page">
      <div className="page-heading">
        <div>
          <span className="eyebrow">KNOWLEDGE BASE</span>
          <h1>文档库</h1>
          <p>
            {user.role === "admin"
              ? "全部部门"
              : user.department || "未分配部门"}
            <span className="heading-separator">/</span>
            {data ? `${data.total} 份文档` : "加载中"}
          </p>
        </div>
        <div className="heading-actions">
          <IconButton
            label="刷新"
            disabled={busy || loading}
            onClick={() => {
              setLoading(true);
              void load();
            }}
          >
            <FiRefreshCw className={loading ? "spin" : ""} />
          </IconButton>
          {user.role !== "employee" && (
            <button
              className="button primary"
              disabled={busy}
              onClick={() => uploadInput.current?.click()}
            >
              <FiUpload />
              {busy ? "处理中…" : "上传文档"}
            </button>
          )}
        </div>
      </div>
      {user.role !== "employee" && (
        <input
          ref={uploadInput}
          aria-label="上传文档"
          type="file"
          accept=".txt,.md,.pdf,.docx"
          className="sr-only"
          disabled={busy}
          onChange={(event) => {
            const file = event.currentTarget.files?.[0];
            event.currentTarget.value = "";
            if (file)
              void action(
                () =>
                  uploadDocument(
                    file,
                    user.role === "admin"
                      ? uploadDepartment.trim() || undefined
                      : user.department || undefined,
                  ),
                "文档已加入处理队列",
              );
          }}
        />
      )}
      <div className="document-toolbar">
        <label className="search-field">
          <FiSearch />
          <input
            aria-label="搜索本页文档"
            placeholder="搜索本页文档"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
          {search && (
            <IconButton label="清空搜索" onClick={() => setSearch("")}>
              <FiX />
            </IconButton>
          )}
        </label>
        <label className="filter-field">
          <FiFilter />
          <select
            aria-label="文档状态"
            value={status}
            onChange={(event) => {
              setPage(1);
              setStatus(event.target.value);
            }}
          >
            <option value="">全部状态</option>
            <option value="ready">可检索</option>
            <option value="pending">等待处理</option>
            <option value="processing">处理中</option>
            <option value="error">处理失败</option>
          </select>
        </label>
        {user.role === "admin" && (
          <label className="upload-department">
            上传部门
            <input
              aria-label="上传部门"
              maxLength={128}
              placeholder="未分配"
              value={uploadDepartment}
              onChange={(event) => setUploadDepartment(event.target.value)}
            />
          </label>
        )}
      </div>
      {error && (
        <div className="notice error" role="alert">
          {error}
        </div>
      )}
      {actionError && !deleting && (
        <div className="notice error" role="alert">
          {actionError}
        </div>
      )}
      {message && (
        <div className="notice success" role="status">
          {message}
        </div>
      )}
      <div className="document-list" aria-busy={loading}>
        <table className="data-table document-table">
          <thead>
            <tr>
              <th>文档名称</th>
              <th>部门</th>
              <th>状态</th>
              <th>片段</th>
              <th>更新于</th>
              <th className="actions-column">操作</th>
            </tr>
          </thead>
          <tbody>
            {visible.map((doc) => (
              <tr key={doc.id}>
                <td className="document-title-cell">
                  <div className="document-title">
                    <span
                      className={`file-symbol ${doc.file_type}`}
                      aria-hidden="true"
                    >
                      <FiFileText />
                    </span>
                    <div>
                      <strong>{doc.title}</strong>
                      <span className="document-meta">
                        {doc.file_type.toUpperCase()}
                        <span>·</span>
                        {formatSize(doc.file_size)}
                        <span>·</span>v{doc.version}
                      </span>
                      {doc.error_message && (
                        <details className="document-error">
                          <summary>查看失败原因</summary>
                          <p>{doc.error_message}</p>
                        </details>
                      )}
                    </div>
                  </div>
                </td>
                <td className="document-department" data-label="部门">
                  {doc.department || "未分配"}
                </td>
                <td className="document-status">
                  <StatusBadge status={doc.status} />
                </td>
                <td className="document-chunks" data-label="片段">
                  {doc.chunk_count}
                </td>
                <td className="document-date" data-label="更新于">
                  {formatDate(doc.updated_at)}
                </td>
                <td className="document-actions">
                  <div className="row-actions">
                    {user.role !== "employee" ? (
                      <>
                        {doc.status === "error" && (
                          <IconButton
                            label="重试处理"
                            disabled={busy}
                            onClick={() =>
                              void action(
                                () => documentAction(doc.id, "retry"),
                                "已重新加入处理队列",
                              )
                            }
                          >
                            <FiRefreshCw />
                          </IconButton>
                        )}
                        <IconButton
                          label={`删除 ${doc.title}`}
                          className="destructive"
                          disabled={busy}
                          onClick={() => {
                            setActionError("");
                            setDeleting(doc);
                          }}
                        >
                          <FiTrash2 />
                        </IconButton>
                      </>
                    ) : (
                      <button
                        className="text-button"
                        disabled={busy}
                        onClick={() =>
                          void action(
                            () => documentAction(doc.id, "review"),
                            "删除申请已提交",
                          )
                        }
                      >
                        <FiTrash2 />
                        申请删除
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!visible.length && (
          <EmptyState
            icon={loading ? <FiRefreshCw className="spin" /> : <FiFileText />}
            title={
              loading
                ? "正在加载文档"
                : search || status
                  ? "没有匹配的文档"
                  : "暂无文档"
            }
          >
            {(search || status) && !loading && (
              <button
                className="text-button"
                onClick={() => {
                  setSearch("");
                  setStatus("");
                  setPage(1);
                }}
              >
                清除筛选
              </button>
            )}
          </EmptyState>
        )}
      </div>
      <div className="table-footer">
        <span>
          共 {data?.total || 0} 份<span className="footer-divider">·</span>每页
          20 份
        </span>
        <div className="pagination">
          <IconButton
            label="上一页"
            disabled={page <= 1 || loading}
            onClick={() => setPage(page - 1)}
          >
            <FiChevronLeft />
          </IconButton>
          <span>
            {page} / {pageCount}
          </span>
          <IconButton
            label="下一页"
            disabled={page >= pageCount || loading}
            onClick={() => setPage(page + 1)}
          >
            <FiChevronRight />
          </IconButton>
        </div>
      </div>
      {deleting && (
        <ConfirmDialog
          title="删除文档"
          description={`确定删除“${deleting.title}”？文档及其检索数据将被移除。`}
          confirmLabel="删除文档"
          danger
          error={actionError}
          busy={busy}
          onClose={() => setDeleting(null)}
          onConfirm={() => {
            void action(async () => {
              await deleteDocument(deleting.id);
              setDeleting(null);
            }, "文档已删除");
          }}
        />
      )}
    </section>
  );
}
