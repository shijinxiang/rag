// Isolated UI checks: all API requests are intercepted; no business data or keys are changed.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");

const baseURL = process.env.FRONTEND_URL || "http://127.0.0.1:3100";
const output =
  process.env.CHECK_OUTPUT || path.resolve(__dirname, "../results/ui");
const date = "2026-10-10T09:00:00Z";
const makeDocuments = () =>
  Array.from({ length: 25 }, (_, index) => ({
    id: `document-${index}`,
    title: [
      "员工手册与年假申请流程.pdf",
      "差旅费用报销管理办法.docx",
      "产品知识库常见问题.md",
      "跨部门协作规范与完整说明_abcdefghijklmnopqrstuvwxyz0123456789.txt",
    ][index % 4],
    file_type: ["pdf", "docx", "md", "txt"][index % 4],
    file_size: 245760 + index * 1024,
    status: ["ready", "pending", "processing", "error"][index % 4],
    version: 1,
    department: ["人事部", "财务部", "产品部", "运营部"][index % 4],
    access_level: 1,
    chunk_count: index % 4 ? 0 : 24,
    error_message: index % 4 === 3 ? "尚未配置模型凭据，请稍后重试。" : null,
    created_at: date,
    updated_at: date,
  }));
const source = {
  index: 1,
  doc_title: "员工手册与年假申请流程.pdf",
  doc_id: "document-0",
  chunk_id: "chunk-0",
  page_number: 3,
  score: 0.92,
  excerpt: "员工通过人事系统提交年假申请，由直属经理审批。",
};
const answer =
  "## 年假申请\n\n1. 在人事系统中提交申请。\n2. 由直属经理审批。\n\n**审批通过后**，申请状态更新为已批准。[1]";

async function checkLayout(page, name) {
  const result = await page.evaluate(() => {
    const viewport = window.innerWidth;
    const overflow = [
      ...document.querySelectorAll("h1,h2,button,input,textarea"),
    ]
      .filter((element) => {
        const rect = element.getBoundingClientRect();
        return (
          rect.width &&
          rect.height &&
          getComputedStyle(element).visibility !== "hidden" &&
          !element.closest(".table-scroll") &&
          (rect.right > viewport + 1 || rect.left < -1)
        );
      })
      .map(
        (element) =>
          element.getAttribute("aria-label") ||
          element.textContent.slice(0, 40),
      );
    const edges = [...document.querySelectorAll("*")]
      .filter((element) => {
        const rect = element.getBoundingClientRect();
        return (
          rect.width &&
          rect.height &&
          rect.right > viewport + 1 &&
          !element.closest(".table-scroll")
        );
      })
      .map((element) => ({
        tag: element.tagName,
        css: element.className,
        right: element.getBoundingClientRect().right,
      }));
    return {
      viewport,
      width: document.documentElement.scrollWidth,
      overflow,
      edges,
    };
  });
  assert(result.width <= result.viewport, `${name}: ${JSON.stringify(result)}`);
  assert.deepEqual(result.overflow, [], `${name}: controls overflow`);
}

async function main() {
  fs.mkdirSync(output, { recursive: true });
  const browser = await chromium.launch({ headless: true, channel: "chrome" });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    permissions: ["clipboard-read", "clipboard-write"],
  });
  const page = await context.newPage();
  const errors = [];
  const unexpected = [];
  page.on("pageerror", (error) => errors.push(error.message));
  let loggedIn = false;
  let role = "admin";
  let documents = makeDocuments();
  let deleteFailure = true;
  let reviewFailure = true;
  let keyConfigured = false;
  let slow = false;
  let queryFailure = false;
  let pendingReviews = ["a", "b"].map((id) => ({
    id,
    action: "document.delete",
    status: "pending",
    payload: {
      document_id: "document-0",
      document_title: "员工手册与年假申请流程.pdf",
    },
    created_at: date,
  }));
  const user = () => ({
    id: "ui-user",
    username: "knowledge-admin",
    role,
    department: "人事部",
  });
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const endpoint = url.pathname.replace("/api/v1", "");
    const json = (value, status = 200) =>
      route.fulfill({
        status,
        contentType: "application/json",
        body: JSON.stringify(value),
      });
    if (endpoint === "/health")
      return json({ status: "healthy", version: "1.0.0", environment: "test" });
    if (endpoint === "/auth/me")
      return loggedIn
        ? json(user())
        : json({ detail: "Authentication required" }, 401);
    if (
      endpoint === "/auth/login" ||
      endpoint === "/auth/register" ||
      endpoint === "/auth/refresh"
    ) {
      const body = request.postDataJSON();
      if (body.password === "invalid-password")
        return json({ detail: "用户名或密码错误" }, 401);
      loggedIn = true;
      return json({
        access_token: "ui-access-token",
        refresh_token: "ui-refresh-token",
        user: user(),
      });
    }
    if (endpoint === "/documents") {
      const filtered = documents.filter(
        (item) =>
          !url.searchParams.get("status") ||
          item.status === url.searchParams.get("status"),
      );
      const current = Number(url.searchParams.get("page") || 1);
      const size = Number(url.searchParams.get("page_size") || 20);
      return json({
        items: filtered.slice((current - 1) * size, current * size),
        total: filtered.length,
        page: current,
        page_size: size,
        pages: Math.max(1, Math.ceil(filtered.length / size)),
      });
    }
    if (endpoint === "/documents/upload") {
      const doc = {
        ...documents[0],
        id: "uploaded",
        title: "uploaded.txt",
        status: "pending",
        file_type: "txt",
      };
      documents.unshift(doc);
      return json(doc, 201);
    }
    if (request.method() === "DELETE" && endpoint.startsWith("/documents/")) {
      if (deleteFailure) {
        deleteFailure = false;
        return json({ detail: "删除失败，请重试" }, 503);
      }
      documents = documents.filter(
        (item) => item.id !== endpoint.split("/")[2],
      );
      return route.fulfill({ status: 204 });
    }
    if (endpoint.endsWith("/retry")) {
      const doc = documents.find((item) => item.id === endpoint.split("/")[2]);
      doc.status = "pending";
      return json(doc);
    }
    if (endpoint.endsWith("/review")) return json({ status: "pending" }, 201);
    if (endpoint === "/admin/reviews") return json(pendingReviews);
    if (/^\/admin\/reviews\/[^/]+\/(approve|reject)$/.test(endpoint)) {
      if (reviewFailure) {
        reviewFailure = false;
        return json({ detail: "审核提交失败" }, 503);
      }
      pendingReviews = pendingReviews.filter(
        (item) => item.id !== endpoint.split("/")[3],
      );
      return json({ status: "approved" });
    }
    if (endpoint === "/admin/audit-logs")
      return json(
        documents
          .slice(0, 8)
          .map((item, index) => ({
            id: `audit-${index}`,
            action: index === 3 ? "document.queue_failed" : "document.upload",
            outcome: index === 3 ? "error" : "success",
            resource_id: item.id,
            created_at: date,
          })),
      );
    if (endpoint === "/admin/settings/openai") {
      if (request.method() === "PUT") {
        if (!request.postDataJSON().api_key.startsWith("sk-"))
          return json(
            { detail: [{ msg: "请输入有效的 OpenAI API Key" }] },
            422,
          );
        keyConfigured = true;
        return json({
          configured: true,
          masked: "sk-ui...1234",
          restart_required: true,
        });
      }
      return json({
        configured: keyConfigured,
        masked: keyConfigured ? "sk-ui...1234" : null,
      });
    }
    if (endpoint === "/queries" || endpoint === "/queries/stream") {
      if (queryFailure) return json({ detail: "模型服务暂时不可用" }, 503);
      if (slow) await new Promise((resolve) => setTimeout(resolve, 1500));
      if (endpoint === "/queries")
        return json({
          query_id: "query",
          question: request.postDataJSON().question,
          answer,
          sources: [source],
          retrieval_count: 1,
        });
      const frame = (event, data) =>
        `event: ${event}\ndata: ${data.split("\n").join("\ndata: ")}\n\n`;
      return route.fulfill({
        contentType: "text/event-stream",
        body:
          frame("sources", JSON.stringify([source])) +
          frame("token", answer) +
          frame("done", "{}"),
      });
    }
    unexpected.push(`${request.method()} ${endpoint}`);
    return json({ detail: "Unexpected UI test endpoint" }, 500);
  });
  try {
    await page.goto(baseURL);
    await page.getByRole("heading", { name: "登录知识库" }).waitFor();
    await checkLayout(page, "login desktop");
    await page.screenshot({
      path: path.join(output, "login-desktop.png"),
      fullPage: true,
    });
    await page.getByLabel("用户名", { exact: true }).fill("ui-tester");
    await page.getByLabel("密码", { exact: true }).fill("invalid-password");
    await page.getByRole("button", { name: "登录", exact: true }).click();
    await page
      .getByRole("alert")
      .filter({ hasText: "用户名或密码错误" })
      .waitFor();
    await page.getByRole("tab", { name: "创建账号" }).click();
    await page.getByLabel("用户名", { exact: true }).fill("ui-tester");
    await page.getByLabel("邮箱").fill("ui-test@example.com");
    await page.getByLabel("部门", { exact: true }).fill("人事部");
    await page.getByLabel("密码", { exact: true }).fill("ui-test-password");
    await page.getByRole("button", { name: "显示密码" }).click();
    assert.equal(
      await page.getByLabel("密码", { exact: true }).getAttribute("type"),
      "text",
    );
    await page.getByRole("button", { name: "注册", exact: true }).click();
    await page.getByRole("tab", { name: "问答", exact: true }).waitFor();
    await page.screenshot({
      path: path.join(output, "chat-desktop.png"),
      fullPage: true,
    });
    await page.getByRole("button", { name: /公司年假怎么申请/ }).click();
    assert.equal(
      await page.getByLabel("输入问题").inputValue(),
      "公司年假怎么申请？",
    );
    await page.getByRole("button", { name: "发送问题" }).click();
    await page
      .getByRole("heading", { name: "年假申请", exact: true })
      .waitFor();
    await page.locator(".sources > summary").click();
    await page.getByText(source.excerpt, { exact: true }).waitFor();
    await page.getByRole("button", { name: "复制答案" }).click();
    await page.getByRole("button", { name: "已复制" }).waitFor();
    await page.getByRole("tab", { name: "文档", exact: true }).click();
    await page
      .locator(".page-heading p")
      .filter({ hasText: "25 份文档" })
      .waitFor();
    await page.screenshot({ path: path.join(output, "documents-desktop.png") });
    await page.getByRole("button", { name: "下一页" }).click();
    await page.getByText("2 / 2", { exact: true }).waitFor();
    await page.getByRole("button", { name: "上一页" }).click();
    await page.getByLabel("搜索本页文档").fill("不存在的文件");
    await page.getByRole("heading", { name: "没有匹配的文档" }).waitFor();
    await page.getByRole("button", { name: "清空搜索" }).click();
    await page.getByLabel("文档状态").selectOption("error");
    await page.getByRole("button", { name: "重试处理" }).first().click();
    await page.getByText("已重新加入处理队列", { exact: true }).waitFor();
    await page.getByLabel("文档状态").selectOption("");
    await page
      .getByRole("button", { name: /^删除 / })
      .first()
      .click();
    await page.getByRole("dialog", { name: "删除文档" }).waitFor();
    await page.getByRole("button", { name: "取消", exact: true }).click();
    await page
      .getByRole("button", { name: /^删除 / })
      .first()
      .click();
    await page
      .getByRole("dialog")
      .getByRole("button", { name: "删除文档", exact: true })
      .click();
    await page
      .getByRole("dialog")
      .getByRole("alert")
      .filter({ hasText: "删除失败" })
      .waitFor();
    await page
      .getByRole("dialog")
      .getByRole("button", { name: "删除文档", exact: true })
      .click();
    await page.getByRole("dialog").waitFor({ state: "hidden" });
    await page
      .getByLabel("上传文档")
      .setInputFiles({
        name: "uploaded.txt",
        mimeType: "text/plain",
        buffer: Buffer.from("UI test fixture"),
      });
    await page.getByText("文档已加入处理队列", { exact: true }).waitFor();
    await page.getByRole("tab", { name: "审核与审计" }).click();
    await page
      .getByRole("heading", { name: "审计日志", exact: true })
      .waitFor();
    await page
      .getByRole("button", { name: "批准", exact: true })
      .first()
      .click();
    await page
      .getByRole("dialog")
      .getByRole("button", { name: "批准", exact: true })
      .click();
    await page
      .getByRole("dialog")
      .getByRole("alert")
      .filter({ hasText: "审核提交失败" })
      .waitFor();
    await page
      .getByRole("dialog")
      .getByRole("button", { name: "批准", exact: true })
      .click();
    await page.getByRole("dialog").waitFor({ state: "hidden" });
    await page
      .getByRole("button", { name: "拒绝", exact: true })
      .first()
      .click();
    await page
      .getByRole("dialog")
      .getByRole("button", { name: "拒绝", exact: true })
      .click();
    await page.getByRole("heading", { name: "暂无待审核请求" }).waitFor();
    await page.getByLabel("审计结果").selectOption("error");
    assert.equal(await page.locator(".audit-table tbody tr").count(), 1);
    await page.getByRole("tab", { name: "模型配置" }).click();
    await page
      .getByLabel("OpenAI API Key", { exact: true })
      .fill("invalid-key-for-ui-only");
    await page.getByRole("button", { name: "保存 Key" }).click();
    await page.getByRole("alert").filter({ hasText: "请输入有效" }).waitFor();
    await page
      .getByLabel("OpenAI API Key", { exact: true })
      .fill("sk-ui-test-only-key-1234");
    await page.getByRole("button", { name: "显示密钥" }).click();
    await page.getByRole("button", { name: "保存 Key" }).click();
    await page
      .getByText("密钥已保存，需重启服务后生效。", { exact: true })
      .waitFor();
    assert.equal(
      await page.getByLabel("替换 API Key", { exact: true }).inputValue(),
      "",
    );
    assert.equal(
      await page
        .getByLabel("替换 API Key", { exact: true })
        .getAttribute("type"),
      "password",
    );
    await page.screenshot({
      path: path.join(output, "settings-desktop.png"),
      fullPage: true,
    });
    for (const viewport of [
      { width: 1440, height: 900 },
      { width: 768, height: 1024 },
      { width: 390, height: 844 },
      { width: 320, height: 568 },
    ]) {
      await page.setViewportSize(viewport);
      for (const name of ["问答", "文档", "审核与审计", "模型配置"]) {
        await page.getByRole("tab", { name, exact: true }).click();
        await checkLayout(page, `${viewport.width} ${name}`);
        if (viewport.width === 390)
          await page.screenshot({
            path: path.join(
              output,
              `${name === "问答" ? "chat" : name === "文档" ? "documents" : name === "审核与审计" ? "admin" : "settings"}-mobile.png`,
            ),
          });
      }
    }
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.getByRole("tab", { name: "问答", exact: true }).click();
    await page
      .getByRole("heading", { name: "年假申请", exact: true })
      .waitFor();
    await page.getByRole("button", { name: "新建对话" }).click();
    await page
      .getByRole("dialog")
      .getByRole("button", { name: "新建对话", exact: true })
      .click();
    slow = true;
    await page.getByLabel("输入问题").fill("停止测试");
    await page.getByRole("button", { name: "发送问题" }).click();
    await page.getByRole("button", { name: "停止生成" }).click();
    await page.getByText("已停止生成", { exact: true }).waitFor();
    slow = false;
    queryFailure = true;
    await page.getByLabel("输入问题").fill("失败测试");
    await page.getByRole("button", { name: "发送问题" }).click();
    await page
      .getByRole("alert")
      .filter({ hasText: "模型服务暂时不可用" })
      .waitFor();
    queryFailure = false;
    await page.getByRole("button", { name: "重新提问" }).click();
    await page
      .getByRole("heading", { name: "年假申请", exact: true })
      .waitFor();
    await page.getByLabel("流式输出").uncheck();
    await page.getByLabel("输入问题").fill("非流式测试");
    await page.getByRole("button", { name: "发送问题" }).click();
    await page.getByRole("button", { name: "复制答案" }).nth(1).waitFor();
    for (const nextRole of ["employee", "manager"]) {
      role = nextRole;
      await page.reload();
      await page.getByRole("tab", { name: "文档", exact: true }).click();
      assert.equal(
        await page.getByRole("tab", { name: "模型配置" }).count(),
        0,
      );
      assert.equal(
        await page.getByLabel("上传文档").count(),
        nextRole === "employee" ? 0 : 1,
      );
      if (nextRole === "employee") {
        await page.getByRole("button", { name: "申请删除" }).first().click();
        await page.getByText("删除申请已提交", { exact: true }).waitFor();
      }
    }
    await page.getByRole("button", { name: "退出登录" }).click();
    await page.getByRole("heading", { name: "登录知识库" }).waitFor();
    await page.setViewportSize({ width: 390, height: 844 });
    await checkLayout(page, "mobile login");
    await page.screenshot({
      path: path.join(output, "login-mobile.png"),
      fullPage: true,
    });
    assert.deepEqual(errors, []);
    assert.deepEqual(unexpected, []);
    console.log(
      "PASS: isolated UI registration/login, stream/non-stream/cancel/retry/copy, document search/filter/page/upload/delete, approval/rejection, key form, roles, logout, four viewports",
    );
    console.log(`Screenshots: ${output}`);
  } catch (error) {
    await page.screenshot({
      path: path.join(output, "failure.png"),
      fullPage: true,
    });
    throw error;
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
