"use client";

import { useEffect, useState, type FormEvent, type KeyboardEvent } from "react";
import {
  FiArrowRight,
  FiBookOpen,
  FiEye,
  FiEyeOff,
  FiFileText,
  FiLayers,
  FiLogOut,
  FiMessageSquare,
  FiSettings,
  FiShield,
  FiWifiOff,
} from "react-icons/fi";
import {
  authenticate,
  currentUser,
  healthCheck,
  logout,
  type UserInfo,
} from "@/lib/api";
import { Brand, errorMessage, IconButton } from "@/components/ui";
import Documents from "@/components/documents";
import Administration from "@/components/administration";
import ModelSettings from "@/components/model-settings";

const navigation = [
  { id: "chat", label: "问答", icon: FiMessageSquare },
  { id: "documents", label: "文档", icon: FiFileText },
  { id: "admin", label: "审核与审计", icon: FiShield, admin: true },
  { id: "settings", label: "模型配置", icon: FiSettings, admin: true },
];
const roles: Record<string, string> = {
  admin: "管理员",
  manager: "部门经理",
  employee: "成员",
};

function navigateTabs(event: KeyboardEvent<HTMLElement>) {
  const tabs = Array.from(
    event.currentTarget.querySelectorAll<HTMLButtonElement>(
      'button[role="tab"]',
    ),
  );
  const current = tabs.indexOf(event.target as HTMLButtonElement);
  if (
    current < 0 ||
    ![
      "ArrowLeft",
      "ArrowRight",
      "ArrowUp",
      "ArrowDown",
      "Home",
      "End",
    ].includes(event.key)
  )
    return;
  event.preventDefault();
  const next =
    event.key === "Home"
      ? 0
      : event.key === "End"
        ? tabs.length - 1
        : (current +
            (["ArrowLeft", "ArrowUp"].includes(event.key) ? -1 : 1) +
            tabs.length) %
          tabs.length;
  tabs[next].focus();
  tabs[next].click();
}

export default function Workspace({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<UserInfo | null>(null);
  const [ready, setReady] = useState(false);
  const [register, setRegister] = useState(false);
  const [tab, setTab] = useState("chat");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [service, setService] = useState<"checking" | "online" | "offline">(
    "checking",
  );

  useEffect(() => {
    let active = true;
    currentUser()
      .then((value) => {
        if (active) setUser(value);
      })
      .catch(() => {})
      .finally(() => {
        if (active) setReady(true);
      });
    return () => {
      active = false;
    };
  }, []);
  useEffect(() => {
    let active = true;
    const check = () =>
      healthCheck()
        .then((value) => {
          if (active)
            setService(value.status === "healthy" ? "online" : "offline");
        })
        .catch(() => {
          if (active) setService("offline");
        });
    void check();
    const timer = setInterval(check, 30000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, []);

  async function signIn(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusy(true);
    setError("");
    try {
      setUser(
        await authenticate(
          String(form.get("username")).trim(),
          String(form.get("password")),
          register ? String(form.get("email")).trim() : undefined,
          register ? String(form.get("department")).trim() : undefined,
        ),
      );
      setShowPassword(false);
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setBusy(false);
    }
  }

  function signOut() {
    logout();
    setUser(null);
    setTab("chat");
    setError("");
    setRegister(false);
    setShowPassword(false);
  }

  const connection = (
    <span className={`connection ${service}`} role="status">
      {service === "offline" ? <FiWifiOff /> : <span className="status-dot" />}
      {service === "online"
        ? "服务正常"
        : service === "offline"
          ? "服务未连接"
          : "连接中"}
    </span>
  );
  if (!ready)
    return (
      <div className="boot-screen">
        <Brand />
        <span className="loading-line" role="status">
          正在连接工作台…
        </span>
      </div>
    );

  if (!user)
    return (
      <div className="auth-shell">
        <header className="auth-header">
          <Brand />
          {connection}
        </header>
        <main className="auth-main">
          <div className="auth-form-wrap">
            <span className="auth-emblem" aria-hidden="true">
              <FiBookOpen />
            </span>
            <h1>{register ? "创建账号" : "登录知识库"}</h1>
            <div
              className="auth-mode"
              role="tablist"
              aria-label="账号入口"
              onKeyDown={navigateTabs}
            >
              <button
                type="button"
                role="tab"
                aria-selected={!register}
                tabIndex={register ? -1 : 0}
                disabled={busy}
                onClick={() => {
                  setRegister(false);
                  setError("");
                }}
              >
                登录
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={register}
                tabIndex={register ? 0 : -1}
                disabled={busy}
                onClick={() => {
                  setRegister(true);
                  setError("");
                }}
              >
                创建账号
              </button>
            </div>
            <form
              key={register ? "register" : "login"}
              onSubmit={signIn}
              className="auth-form"
            >
              <label className="field">
                用户名
                <input
                  name="username"
                  required
                  minLength={3}
                  maxLength={128}
                  autoComplete="username"
                  placeholder="输入用户名"
                  disabled={busy}
                />
              </label>
              {register && (
                <>
                  <label className="field">
                    邮箱
                    <input
                      name="email"
                      type="email"
                      required
                      autoComplete="email"
                      placeholder="name@company.com"
                      disabled={busy}
                    />
                  </label>
                  <label className="field">
                    部门
                    <input
                      name="department"
                      required
                      maxLength={128}
                      autoComplete="organization"
                      placeholder="输入所属部门"
                      disabled={busy}
                    />
                  </label>
                </>
              )}
              <label className="field">
                密码
                <span className="input-with-action">
                  <input
                    name="password"
                    aria-label="密码"
                    type={showPassword ? "text" : "password"}
                    required
                    minLength={8}
                    autoComplete={
                      register ? "new-password" : "current-password"
                    }
                    placeholder="输入密码"
                    disabled={busy}
                  />
                  <IconButton
                    label={showPassword ? "隐藏密码" : "显示密码"}
                    onClick={() => setShowPassword(!showPassword)}
                  >
                    {showPassword ? <FiEyeOff /> : <FiEye />}
                  </IconButton>
                </span>
              </label>
              {error && (
                <div className="notice error" role="alert">
                  {error}
                </div>
              )}
              <button className="button primary auth-submit" disabled={busy}>
                {busy ? "提交中…" : register ? "注册" : "登录"}
                <FiArrowRight />
              </button>
            </form>
          </div>
        </main>
        <footer className="auth-footer">
          <FiShield />
          企业知识工作台<span>RAG / 1.0</span>
        </footer>
      </div>
    );

  const activePage = navigation.find((item) => item.id === tab)!;
  return (
    <div className="workspace-shell">
      <aside className="sidebar">
        <Brand />
        <div className="sidebar-label">工作空间</div>
        <nav
          className="workspace-nav"
          role="tablist"
          aria-label="工作空间"
          onKeyDown={navigateTabs}
        >
          {navigation
            .filter((item) => !item.admin || user.role === "admin")
            .map((item) => (
              <button
                key={item.id}
                id={`tab-${item.id}`}
                role="tab"
                aria-selected={tab === item.id}
                tabIndex={tab === item.id ? 0 : -1}
                aria-controls={`panel-${item.id}`}
                onClick={() => setTab(item.id)}
              >
                <item.icon />
                <span>{item.label}</span>
              </button>
            ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="workspace-scope">
            <FiShield />
            <span>
              {user.role === "admin"
                ? "企业全部部门"
                : user.department || "未分配部门"}
            </span>
          </div>
          {connection}
        </div>
      </aside>
      <div className="workspace-body">
        <header className="workspace-header">
          <div className="breadcrumbs">
            <FiLayers aria-hidden="true" />
            <span>工作空间</span>
            <span className="breadcrumb-divider">/</span>
            <strong>{activePage.label}</strong>
          </div>
          <div className="account">
            <span className="account-avatar" aria-hidden="true">
              {user.username.slice(0, 1).toUpperCase()}
            </span>
            <span className="account-copy">
              <strong>{user.username}</strong>
              <span>{roles[user.role] || user.role}</span>
            </span>
            <IconButton label="退出登录" onClick={signOut}>
              <FiLogOut />
            </IconButton>
          </div>
        </header>
        <main
          className={`workspace-content ${tab === "chat" ? "chat-content" : ""}`}
        >
          <div
            key={user.id}
            id="panel-chat"
            role="tabpanel"
            aria-labelledby="tab-chat"
            hidden={tab !== "chat"}
          >
            {children}
          </div>
          {tab === "documents" && (
            <div
              id="panel-documents"
              role="tabpanel"
              aria-labelledby="tab-documents"
            >
              <Documents user={user} />
            </div>
          )}
          {tab === "admin" && user.role === "admin" && (
            <div id="panel-admin" role="tabpanel" aria-labelledby="tab-admin">
              <Administration />
            </div>
          )}
          {tab === "settings" && user.role === "admin" && (
            <div
              id="panel-settings"
              role="tabpanel"
              aria-labelledby="tab-settings"
            >
              <ModelSettings />
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
