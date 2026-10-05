// Run with PLAYWRIGHT_MODULE pointing to an external Playwright installation.
const assert = require("node:assert/strict");
const { randomUUID } = require("node:crypto");
const { execFileSync } = require("node:child_process");
const path = require("node:path");
const fs = require("node:fs");
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");

const baseURL = process.env.FRONTEND_URL || "http://localhost:3000";
const username = `ui-verify-${randomUUID().replaceAll("-", "")}`;
const password = randomUUID();
const docker = process.env.DOCKER_CLI || "docker";
const root = path.resolve(__dirname, "..");
const output = process.env.CHECK_OUTPUT || path.join(root, "results");
const createdDocuments = [];

function backendPython(code, ...args) {
  return execFileSync(docker, ["exec", "-e", "APP_DEBUG=false", "rag-backend", "python", "-c", code, ...args], { cwd: root, encoding: "utf8" });
}

function promote(role) {
  backendPython("import sys; from sqlalchemy import create_engine,update; from sqlalchemy.orm import Session; from app.config import settings; from app.models.user import User; engine=create_engine(settings.DATABASE_URL_SYNC); db=Session(engine); db.execute(update(User).where(User.username==sys.argv[1]).values(role=sys.argv[2])); db.commit(); db.close(); engine.dispose()", username, role);
}

async function checkWidth(page) {
  const sizes = await page.evaluate(() => ({ content: document.documentElement.scrollWidth, viewport: window.innerWidth }));
  assert(sizes.content <= sizes.viewport, JSON.stringify(sizes));
}

async function main() {
  fs.mkdirSync(output, { recursive: true });
  const browser = await chromium.launch({ headless: true, channel: "chrome" });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  try {
    await page.goto(baseURL);
    await page.getByRole("button", { name: "创建账号", exact: true }).click();
    await page.getByLabel("用户名").fill(username);
    await page.getByLabel("邮箱").fill(`${username}@example.com`);
    await page.getByLabel("部门", { exact: true }).fill("ui-verify");
    await page.getByLabel("密码").fill(password);
    await page.getByRole("button", { name: "注册", exact: true }).click();
    await page.getByRole("tab", { name: "问答", exact: true }).waitFor();
    await checkWidth(page);
    await page.evaluate(() => sessionStorage.setItem("rag_access_token", "expired-invalid-token"));
    await page.reload();
    await page.getByRole("tab", { name: "文档", exact: true }).click();
    await page.getByText("暂无文档", { exact: true }).waitFor();
    assert.equal(await page.getByLabel("上传文档").count(), 0);
    await page.screenshot({ path: path.join(output, "frontend-desktop.png"), fullPage: true });

    promote("manager");
    await page.reload();
    await page.getByRole("tab", { name: "文档", exact: true }).click();
    const uploadResponse = page.waitForResponse((response) => response.url().includes("/documents/upload") && response.status() === 201);
    await page.getByLabel("上传文档").setInputFiles({ name: `${username}.txt`, mimeType: "text/plain", buffer: Buffer.alloc(0) });
    const document = await (await uploadResponse).json();
    createdDocuments.push(document.id);
    await page.getByRole("button", { name: "重试处理", exact: true }).waitFor({ timeout: 45000 });
    await page.getByRole("button", { name: "重试处理", exact: true }).click();
    await page.getByRole("button", { name: "重试处理", exact: true }).waitFor({ timeout: 45000 });

    promote("admin");
    await page.reload();
    await page.getByRole("tab", { name: "文档", exact: true }).click();
    await page.getByLabel("上传部门").fill("finance");
    await page.getByRole("tab", { name: "审核与审计", exact: true }).click();
    await page.getByRole("heading", { name: "审计日志", exact: true }).waitFor();
    await page.setViewportSize({ width: 390, height: 844 });
    await checkWidth(page);
    await page.screenshot({ path: path.join(output, "frontend-mobile.png"), fullPage: true });
    await page.getByRole("button", { name: "退出登录", exact: true }).click();
    await page.getByRole("button", { name: "登录", exact: true }).waitFor();
    await checkWidth(page);
    await page.getByLabel("用户名").fill(username);
    await page.getByLabel("密码").fill(password);
    await page.getByRole("button", { name: "登录", exact: true }).click();
    await page.getByRole("tab", { name: "问答", exact: true }).waitFor();
    await checkWidth(page);
    assert.deepEqual(errors, []);
    console.log("PASS: browser registration, login, refresh, manager upload/retry, admin views, logout, desktop/mobile layout");
  } finally {
    await browser.close();
    backendPython(`
import json, sys, uuid
from pathlib import Path
from sqlalchemy import create_engine, select, delete
from sqlalchemy.orm import Session
from app.config import settings
from app.models.user import User
from app.models.document import Document, DocumentChunk
from app.models.enterprise import AuditLog, ReviewRequest
from app.db.vector_store import get_vector_store
engine = create_engine(settings.DATABASE_URL_SYNC)
ids = [uuid.UUID(item) for item in json.loads(sys.argv[2])]
with Session(engine) as db:
    user = db.scalar(select(User).where(User.username == sys.argv[1]))
    for doc in db.scalars(select(Document).where(Document.id.in_(ids))):
        Path(doc.file_path).unlink(missing_ok=True)
        get_vector_store().delete_by_doc_id(str(doc.id))
    db.execute(delete(DocumentChunk).where(DocumentChunk.document_id.in_(ids)))
    db.execute(delete(Document).where(Document.id.in_(ids)))
    if user:
        db.execute(delete(ReviewRequest).where(ReviewRequest.user_id == user.id))
        db.execute(delete(AuditLog).where(AuditLog.user_id == user.id))
        db.delete(user)
    db.commit()
engine.dispose()
`, username, JSON.stringify(createdDocuments));
  }
}

main().catch((error) => { console.error(error); process.exitCode = 1; });
