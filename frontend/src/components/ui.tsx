"use client";

import {
  useEffect,
  useRef,
  type ButtonHTMLAttributes,
  type ReactNode,
} from "react";
import { FiLayers, FiX } from "react-icons/fi";

export function Brand({ compact = false }: { compact?: boolean }) {
  return (
    <div className="brand">
      <span className="brand-mark" aria-hidden="true">
        <FiLayers />
      </span>
      <span className="brand-copy">
        <strong>知库</strong>
        {!compact && <span>企业知识工作台</span>}
      </span>
    </div>
  );
}

export function IconButton({
  label,
  children,
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { label: string }) {
  return (
    <button
      type="button"
      aria-label={label}
      className={`icon-button ${className}`}
      {...props}
    >
      {children}
      <span className="icon-tooltip" role="tooltip">
        {label}
      </span>
    </button>
  );
}

export function EmptyState({
  icon,
  title,
  children,
}: {
  icon: ReactNode;
  title: string;
  children?: ReactNode;
}) {
  return (
    <div className="empty-state">
      <span className="empty-icon" aria-hidden="true">
        {icon}
      </span>
      <h3>{title}</h3>
      {children}
    </div>
  );
}

const statuses: Record<string, [string, string]> = {
  pending: ["等待处理", "warning"],
  processing: ["处理中", "info"],
  ready: ["可检索", "success"],
  error: ["处理失败", "danger"],
  success: ["成功", "success"],
  approved: ["已批准", "success"],
  rejected: ["已拒绝", "danger"],
};

export function StatusBadge({
  status,
  label,
}: {
  status: string;
  label?: string;
}) {
  const [defaultLabel, tone] = statuses[status] || [status, "neutral"];
  return (
    <span className={`status-badge ${tone}`}>
      <span className="status-dot" />
      {label || defaultLabel}
    </span>
  );
}

export function ConfirmDialog({
  title,
  description,
  confirmLabel,
  busy,
  onConfirm,
  onClose,
  danger = false,
  error,
}: {
  title: string;
  description: string;
  confirmLabel: string;
  busy: boolean;
  onConfirm: () => void;
  onClose: () => void;
  danger?: boolean;
  error?: string;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current;
    dialog?.showModal();
    return () => dialog?.close();
  }, []);
  return (
    <dialog
      ref={ref}
      className="confirm-dialog"
      aria-labelledby="confirmation-title"
      aria-describedby="confirmation-description"
      onCancel={(event) => {
        event.preventDefault();
        if (!busy) onClose();
      }}
    >
      <div className="dialog-heading">
        <h2 id="confirmation-title">{title}</h2>
        <IconButton label="关闭确认" onClick={onClose} disabled={busy}>
          <FiX />
        </IconButton>
      </div>
      <p id="confirmation-description">{description}</p>
      {error && (
        <div className="notice error dialog-error" role="alert">
          {error}
        </div>
      )}
      <div className="dialog-actions">
        <button className="button secondary" onClick={onClose} disabled={busy}>
          取消
        </button>
        <button
          className={`button ${danger ? "danger" : "primary"}`}
          onClick={onConfirm}
          disabled={busy}
        >
          {busy ? "提交中…" : confirmLabel}
        </button>
      </div>
    </dialog>
  );
}

export function formatDate(value: string) {
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(new Date(value));
}

export function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : "请求失败，请稍后重试";
}
