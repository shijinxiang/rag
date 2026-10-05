"use client";

import { useEffect, useState } from "react";
import { FiLogOut, FiRefreshCw, FiTrash2, FiUpload, FiCheck, FiX } from "react-icons/fi";
import { authenticate, currentUser, logout, listDocuments, uploadDocument, deleteDocument, documentAction, reviews, audits, decideReview, getOpenAISettings, updateOpenAISettings, type UserInfo, type DocumentInfo, type Review, type Audit, type OpenAISettings } from "@/lib/api";

export default function Workspace({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<UserInfo | null>(null);
  const [ready, setReady] = useState(false);
  const [register, setRegister] = useState(false);
  const [tab, setTab] = useState("chat");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [documents, setDocuments] = useState<DocumentInfo[]>([]);
  const [reviewList, setReviewList] = useState<Review[]>([]);
  const [auditList, setAuditList] = useState<Audit[]>([]);
  const [uploadDepartment, setUploadDepartment] = useState("");
  const [openAISettings, setOpenAISettings] = useState<OpenAISettings | null>(null);

  useEffect(() => { currentUser().then(setUser).catch(() => {}).finally(() => setReady(true)); }, []);

  async function reload() {
    if (tab === "documents") setDocuments((await listDocuments(1, 100)).items);
    if (tab === "admin") { setReviewList(await reviews()); setAuditList(await audits()); setOpenAISettings(await getOpenAISettings()); }
  }

  useEffect(() => {
    if (!user || tab === "chat") return;
    const update = () => reload().catch((e: Error) => setError(e.message));
    update();
    const timer = setInterval(update, 5000);
    return () => clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user, tab]);

  async function action(fn: () => Promise<unknown>) {
    setBusy(true); setError("");
    try { await fn(); await reload(); } catch (e) { setError(e instanceof Error ? e.message : "请求失败"); }
    finally { setBusy(false); }
  }

  if (!ready) return <p role="status">加载中...</p>;
  if (!user) return <div className="max-w-sm mx-auto py-12">
    <h2 className="text-xl font-semibold mb-6">{register ? "创建账号" : "登录知识库"}</h2>
    <form className="space-y-4" onSubmit={(e) => {
      e.preventDefault(); const form = new FormData(e.currentTarget);
      void action(async () => { setUser(await authenticate(String(form.get("username")), String(form.get("password")), register ? String(form.get("email")) : undefined, register ? String(form.get("department")) : undefined)); });
    }}>
      <label className="block text-sm">用户名<input className="mt-1 w-full border rounded-md p-2" name="username" required minLength={3} autoComplete="username" /></label>
      {register && <><label className="block text-sm">邮箱<input className="mt-1 w-full border rounded-md p-2" name="email" type="email" required /></label><label className="block text-sm">部门<input className="mt-1 w-full border rounded-md p-2" name="department" required /></label></>}
      <label className="block text-sm">密码<input className="mt-1 w-full border rounded-md p-2" name="password" type="password" required minLength={8} autoComplete={register ? "new-password" : "current-password"} /></label>
      {error && <p className="text-red-700 text-sm" role="alert">{error}</p>}
      <button disabled={busy} className="w-full bg-primary-600 text-white rounded-md p-2">{busy ? "提交中..." : register ? "注册" : "登录"}</button>
    </form>
    <button className="mt-4 text-sm text-primary-700" onClick={() => { setRegister(!register); setError(""); }}>{register ? "返回登录" : "创建账号"}</button>
  </div>;

  return <>
    <div className="flex flex-wrap items-center justify-between gap-3 border-b mb-6 pb-3">
      <div className="flex gap-4" role="tablist">
        {[["chat", "问答"], ["documents", "文档"], ...(user.role === "admin" ? [["admin", "审核与审计"]] : [])].map(([id, label]) => <button key={id} role="tab" aria-selected={tab === id} className={`text-sm py-2 ${tab === id ? "text-primary-700 border-b-2 border-primary-600" : "text-gray-600"}`} onClick={() => { setTab(id); setError(""); }}>{label}</button>)}
      </div>
      <div className="flex min-w-0 items-center gap-3 text-sm"><span className="break-all">{user.username} · {user.department || "未分配部门"} · {user.role}</span><button className="shrink-0" title="退出登录" aria-label="退出登录" onClick={() => { logout(); setUser(null); setTab("chat"); setDocuments([]); setReviewList([]); setAuditList([]); setError(""); setUploadDepartment(""); }}><FiLogOut /></button></div>
    </div>
    {error && <p className="text-red-700 text-sm mb-4" role="alert">{error}</p>}
    {tab === "chat" && children}
    {tab === "documents" && <section>
      <div className="flex flex-wrap gap-3 justify-between items-center mb-4"><h2 className="text-lg font-semibold">文档库</h2><div className="flex flex-wrap items-center gap-4">
        <button title="刷新" aria-label="刷新" disabled={busy} onClick={() => void action(reload)}><FiRefreshCw /></button>
        {user.role === "admin" && <label className="flex items-center gap-2 text-sm">部门<input aria-label="上传部门" className="w-32 border rounded-md px-2 py-1" maxLength={128} value={uploadDepartment} onChange={(e) => setUploadDepartment(e.target.value)} /></label>}
        {user.role !== "employee" && <label className="flex gap-2 items-center text-sm text-primary-700 cursor-pointer"><FiUpload />上传<input aria-label="上传文档" type="file" accept=".txt,.md,.pdf,.docx" className="hidden" disabled={busy} onChange={(e) => { const file = e.target.files?.[0]; if (file) void action(() => uploadDocument(file, user.role === "admin" ? uploadDepartment.trim() || undefined : user.department || undefined)); e.target.value = ""; }} /></label>}
      </div></div>
      <div className="overflow-x-auto"><table className="w-full text-sm text-left"><thead className="border-b text-gray-500"><tr><th className="p-3">文档</th><th className="p-3">部门</th><th className="p-3">状态</th><th className="p-3">片段</th><th className="p-3">操作</th></tr></thead><tbody>
        {documents.map((doc) => <tr key={doc.id} className="border-b"><td className="p-3 max-w-sm break-words">{doc.title}{doc.error_message && <p className="text-red-700 text-xs mt-1 break-all">{doc.error_message}</p>}</td><td className="p-3">{doc.department || "未分配"}</td><td className="p-3">{doc.status}</td><td className="p-3">{doc.chunk_count}</td><td className="p-3"><div className="flex gap-4">
          {user.role !== "employee" && <><button title="删除文档" aria-label={`删除 ${doc.title}`} disabled={busy} onClick={() => { if (confirm(`删除 ${doc.title}？`)) void action(() => deleteDocument(doc.id)); }}><FiTrash2 /></button>{doc.status === "error" && <button title="重试处理" aria-label="重试处理" disabled={busy} onClick={() => void action(() => documentAction(doc.id, "retry"))}><FiRefreshCw /></button>}</>}
          {user.role === "employee" && <button disabled={busy} onClick={() => void action(() => documentAction(doc.id, "review"))}>申请删除</button>}
        </div></td></tr>)}
      </tbody></table>{!documents.length && <p className="py-8 text-center text-gray-500">暂无文档</p>}</div>
    </section>}
    {tab === "admin" && user.role === "admin" && <section><h2 className="text-lg font-semibold mb-4">待审核</h2>{reviewList.map((item) => <div key={item.id} className="flex flex-wrap gap-4 justify-between border-b py-3 text-sm"><span className="break-all">{item.action} · {item.payload.document_id}</span><div className="flex gap-4"><button title="批准" aria-label="批准" disabled={busy} onClick={() => void action(() => decideReview(item.id, "approve"))}><FiCheck /></button><button title="拒绝" aria-label="拒绝" disabled={busy} onClick={() => void action(() => decideReview(item.id, "reject"))}><FiX /></button></div></div>)}{!reviewList.length && <p className="text-gray-500 text-sm">暂无待审核请求</p>}
      <h2 className="text-lg font-semibold mt-8 mb-4">模型配置</h2><div className="border rounded-lg p-4 max-w-xl"><p className="text-sm text-gray-600 mb-3">OpenAI API Key 仅保存到服务器 .env，页面不会显示完整密钥。</p><form className="flex flex-wrap gap-2" onSubmit={(e) => { e.preventDefault(); const value = new FormData(e.currentTarget).get("api_key") as string; void action(async () => { const next = await updateOpenAISettings(value); setOpenAISettings(next); e.currentTarget.reset(); }); }}><input name="api_key" type="password" autoComplete="new-password" required minLength={20} placeholder="sk-..." className="flex-1 min-w-56 border rounded-md px-3 py-2 text-sm"/><button className="bg-primary-600 text-white rounded-md px-4 py-2 text-sm" disabled={busy}>保存 Key</button></form><p className="text-xs mt-3" role="status">当前状态：{openAISettings?.configured ? <span className="text-green-700">已配置（{openAISettings.masked}）</span> : <span className="text-amber-700">未配置</span>}</p>{openAISettings?.restart_required && <p className="text-xs text-amber-700 mt-1">配置已保存。请重启 backend 和 celery-worker 后开始真实向量化。</p>}</div>
      <h2 className="text-lg font-semibold mt-8 mb-4">审计日志</h2><div className="overflow-x-auto"><table className="w-full text-sm text-left"><thead><tr><th className="p-2">时间</th><th className="p-2">动作</th><th className="p-2">资源</th><th className="p-2">结果</th></tr></thead><tbody>{auditList.map((item) => <tr key={item.id} className="border-b"><td className="p-2 whitespace-nowrap">{new Date(item.created_at).toLocaleString()}</td><td className="p-2">{item.action}</td><td className="p-2 break-all">{item.resource_id}</td><td className="p-2">{item.outcome}</td></tr>)}</tbody></table></div>
    </section>}
  </>;
}
