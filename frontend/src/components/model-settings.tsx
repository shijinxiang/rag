"use client";

import { useEffect, useState, type FormEvent } from "react";
import {
  FiCheck,
  FiEye,
  FiEyeOff,
  FiKey,
  FiSave,
  FiShield,
} from "react-icons/fi";
import {
  getOpenAISettings,
  updateOpenAISettings,
  type OpenAISettings,
} from "@/lib/api";
import { errorMessage, IconButton } from "@/components/ui";

export default function ModelSettings() {
  const [settings, setSettings] = useState<OpenAISettings | null>(null);
  const [apiKey, setApiKey] = useState("");
  const [visible, setVisible] = useState(false);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    getOpenAISettings()
      .then((value) => {
        if (active) setSettings(value);
      })
      .catch((cause) => {
        if (active) setError(errorMessage(cause));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      setSettings(await updateOpenAISettings(apiKey.trim()));
      setApiKey("");
      setVisible(false);
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="data-page settings-page">
      <div className="page-heading">
        <div>
          <span className="eyebrow">MODEL CONNECTION</span>
          <h1>模型配置</h1>
          <p>OpenAI</p>
        </div>
        <span className="settings-access">
          <FiShield />
          仅管理员
        </span>
      </div>
      <section className="settings-section">
        <div className="section-heading">
          <h2>
            <FiKey />
            API 凭据
          </h2>
          <span
            className={`status-badge ${loading ? "neutral" : settings?.configured ? "success" : "warning"}`}
            role="status"
          >
            <span className="status-dot" />
            {loading
              ? "加载中"
              : !settings && error
                ? "读取失败"
                : settings?.configured
                  ? "已配置"
                  : "未配置"}
          </span>
        </div>
        <dl className="settings-summary">
          <div>
            <dt>服务商</dt>
            <dd>OpenAI</dd>
          </div>
          <div>
            <dt>当前密钥</dt>
            <dd className="masked-key">{settings?.masked || "尚未配置"}</dd>
          </div>
        </dl>
        <form className="settings-form" onSubmit={save}>
          <label className="field">
            {settings?.configured ? "替换 API Key" : "OpenAI API Key"}
            <span className="input-with-action">
              <input
                aria-label={
                  settings?.configured ? "替换 API Key" : "OpenAI API Key"
                }
                name="api_key"
                type={visible ? "text" : "password"}
                autoComplete="off"
                spellCheck={false}
                required
                minLength={20}
                maxLength={500}
                placeholder="sk-…"
                value={apiKey}
                onChange={(event) => setApiKey(event.target.value)}
                disabled={busy || loading}
              />
              <IconButton
                label={visible ? "隐藏密钥" : "显示密钥"}
                onClick={() => setVisible(!visible)}
              >
                {visible ? <FiEyeOff /> : <FiEye />}
              </IconButton>
            </span>
          </label>
          {error && (
            <div className="notice error" role="alert">
              {error}
            </div>
          )}
          {settings?.restart_required && (
            <div className="notice warning" role="status">
              <FiCheck />
              密钥已保存，需重启服务后生效。
            </div>
          )}
          <div className="settings-actions">
            <button
              className="button primary"
              disabled={busy || loading || !apiKey.trim()}
            >
              <FiSave />
              {busy ? "保存中…" : "保存 Key"}
            </button>
          </div>
        </form>
      </section>
    </section>
  );
}
