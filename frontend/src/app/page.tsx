"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import ReactMarkdown from "react-markdown";
import {
  FiArrowRight,
  FiBookOpen,
  FiCheck,
  FiCopy,
  FiCornerUpLeft,
  FiFileText,
  FiMessageSquare,
  FiPlus,
  FiSend,
  FiShield,
  FiSliders,
  FiSquare,
} from "react-icons/fi";
import { askQuestion, streamQuestion, type Source } from "@/lib/api";
import { ConfirmDialog, errorMessage, IconButton } from "@/components/ui";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
  isStreaming?: boolean;
  error?: string;
  cancelled?: boolean;
  question?: string;
}

const suggestions = [
  { topic: "人事制度", question: "公司年假怎么申请？", icon: FiBookOpen },
  { topic: "财务流程", question: "出差报销需要哪些材料？", icon: FiFileText },
  {
    topic: "入职指南",
    question: "新员工入职流程是什么？",
    icon: FiMessageSquare,
  },
];

export default function HomePage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [useStream, setUseStream] = useState(true);
  const [topK, setTopK] = useState(10);
  const [copied, setCopied] = useState("");
  const [copyError, setCopyError] = useState("");
  const [confirmClear, setConfirmClear] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const requestRef = useRef<AbortController | null>(null);
  const copyTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    const area = scrollRef.current;
    if (area) area.scrollTop = area.scrollHeight;
  }, [messages]);
  useEffect(
    () => () => {
      requestRef.current?.abort();
      if (copyTimer.current) clearTimeout(copyTimer.current);
    },
    [],
  );

  async function send(question: string) {
    if (!question.trim() || requestRef.current) return;
    const controller = new AbortController();
    requestRef.current = controller;
    const id = crypto.randomUUID();
    setInput("");
    setLoading(true);
    setCopyError("");
    setMessages((previous) => [
      ...previous,
      { id: crypto.randomUUID(), role: "user", content: question },
      { id, role: "assistant", content: "", isStreaming: true, question },
    ]);
    const update = (changes: Partial<Message>) =>
      setMessages((previous) =>
        previous.map((message) =>
          message.id === id ? { ...message, ...changes } : message,
        ),
      );
    try {
      if (useStream) {
        await streamQuestion(
          question,
          (sources) => update({ sources }),
          (token) =>
            setMessages((previous) =>
              previous.map((message) =>
                message.id === id
                  ? { ...message, content: message.content + token }
                  : message,
              ),
            ),
          () => update({ isStreaming: false }),
          undefined,
          topK,
          undefined,
          controller.signal,
        );
      } else {
        const result = await askQuestion(
          question,
          topK,
          undefined,
          controller.signal,
        );
        update({
          content: result.answer,
          sources: result.sources,
          isStreaming: false,
        });
      }
    } catch (cause) {
      update(
        controller.signal.aborted
          ? { cancelled: true, isStreaming: false }
          : { error: errorMessage(cause), isStreaming: false },
      );
    } finally {
      requestRef.current = null;
      setLoading(false);
      textareaRef.current?.focus();
    }
  }

  async function copy(message: Message) {
    setCopyError("");
    try {
      await navigator.clipboard.writeText(message.content);
      setCopied(message.id);
      if (copyTimer.current) clearTimeout(copyTimer.current);
      copyTimer.current = setTimeout(() => setCopied(""), 2000);
    } catch {
      setCopyError("复制失败，请检查浏览器的剪贴板权限");
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    void send(input.trim());
  }

  return (
    <section className="chat-page">
      <div className="chat-heading">
        <div>
          <span className="eyebrow">KNOWLEDGE ASSISTANT</span>
          <h1>知识问答</h1>
        </div>
        <div className="heading-actions">
          <span className="chat-session">
            {messages.length
              ? `${messages.filter((item) => item.role === "user").length} 次提问`
              : "新对话"}
          </span>
          <IconButton
            label="新建对话"
            disabled={loading || !messages.length}
            onClick={() => setConfirmClear(true)}
          >
            <FiPlus />
          </IconButton>
        </div>
      </div>
      <div
        className="conversation"
        ref={scrollRef}
        aria-label="对话记录"
        role="log"
        aria-live="polite"
        aria-relevant="additions text"
      >
        {!messages.length && (
          <div className="chat-empty">
            <span className="assistant-emblem" aria-hidden="true">
              <FiBookOpen aria-hidden="true" />
            </span>
            <span className="chat-empty-label">企业知识库</span>
            <h2>今天，想了解什么？</h2>
            <div className="suggestions">
              {suggestions.map((item) => (
                <button
                  key={item.topic}
                  onClick={() => {
                    setInput(item.question);
                    textareaRef.current?.focus();
                  }}
                >
                  <item.icon />
                  <span>
                    <span>{item.topic}</span>
                    <strong>{item.question}</strong>
                  </span>
                  <FiArrowRight />
                </button>
              ))}
            </div>
          </div>
        )}
        {messages.map((message) => (
          <article
            key={message.id}
            className={`message ${message.role}`}
            aria-label={message.role === "user" ? "我的问题" : "知识助手的回答"}
          >
            <div className="message-heading">
              <span className="message-avatar" aria-hidden="true">
                {message.role === "assistant" ? <FiBookOpen /> : "我"}
              </span>
              <strong>
                {message.role === "assistant" ? "知识助手" : "我"}
              </strong>
              {message.isStreaming && (
                <span className="message-status" role="status">
                  生成中
                  <span className="typing-dots">
                    <i />
                    <i />
                    <i />
                  </span>
                </span>
              )}
            </div>
            <div className="message-body">
              {message.role === "user" ? (
                <p className="question-text">{message.content}</p>
              ) : (
                <>
                  {message.content && (
                    <div className="prose-custom">
                      <ReactMarkdown>{message.content}</ReactMarkdown>
                    </div>
                  )}
                  {!message.content && message.isStreaming && (
                    <div className="answer-loading">
                      <span className="skeleton" />
                      <span className="skeleton" />
                    </div>
                  )}
                  {message.error && (
                    <div className="notice error" role="alert">
                      {message.error}
                    </div>
                  )}
                  {message.cancelled && (
                    <span className="message-status">已停止生成</span>
                  )}
                  {!!message.sources?.length && !message.isStreaming && (
                    <details className="sources">
                      <summary>
                        <FiFileText />
                        引用来源<span>{message.sources.length}</span>
                      </summary>
                      <div className="source-list">
                        {message.sources.map((source) => (
                          <div
                            key={`${source.index}-${source.chunk_id}`}
                            className="source-item"
                          >
                            <div className="source-title">
                              <span className="source-index">
                                {source.index}
                              </span>
                              <strong>{source.doc_title}</strong>
                              {source.page_number !== null && (
                                <span>第 {source.page_number} 页</span>
                              )}
                            </div>
                            <p>{source.excerpt}</p>
                          </div>
                        ))}
                      </div>
                    </details>
                  )}
                  {!message.isStreaming && (
                    <div className="message-actions">
                      {message.content && (
                        <IconButton
                          label={copied === message.id ? "已复制" : "复制答案"}
                          onClick={() => void copy(message)}
                        >
                          {copied === message.id ? <FiCheck /> : <FiCopy />}
                        </IconButton>
                      )}
                      {message.error && (
                        <button
                          className="text-button"
                          disabled={loading}
                          onClick={() => void send(message.question || "")}
                        >
                          <FiCornerUpLeft />
                          重新提问
                        </button>
                      )}
                    </div>
                  )}
                </>
              )}
            </div>
          </article>
        ))}
      </div>
      <div className="composer-area">
        {copyError && (
          <div className="notice error" role="alert">
            {copyError}
          </div>
        )}
        <form onSubmit={submit} className="composer">
          <textarea
            ref={textareaRef}
            aria-label="输入问题"
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={(event) => {
              if (
                event.key === "Enter" &&
                !event.shiftKey &&
                !event.nativeEvent.isComposing
              ) {
                event.preventDefault();
                if (!loading) void send(input.trim());
              }
            }}
            placeholder="输入你的问题…"
            rows={2}
            maxLength={5000}
            disabled={loading}
          />
          <div className="composer-controls">
            <label className="stream-toggle">
              <input
                type="checkbox"
                checked={useStream}
                disabled={loading}
                onChange={(event) => setUseStream(event.target.checked)}
              />
              <span className="toggle-track" />
              <span>流式输出</span>
            </label>
            <details className="retrieval-control">
              <summary aria-label="检索设置">
                <FiSliders />
              </summary>
              <label>
                检索片段
                <input
                  aria-label="检索片段数量"
                  type="number"
                  min={1}
                  max={50}
                  value={topK}
                  disabled={loading}
                  onChange={(event) =>
                    setTopK(
                      Math.max(
                        1,
                        Math.min(50, Number(event.target.value) || 1),
                      ),
                    )
                  }
                />
              </label>
            </details>
            <span className="composer-count">{input.length} / 5000</span>
            {loading ? (
              <IconButton
                label="停止生成"
                className="send-button"
                onClick={() => requestRef.current?.abort()}
              >
                <FiSquare />
              </IconButton>
            ) : (
              <button
                type="submit"
                className="icon-button send-button"
                aria-label="发送问题"
                disabled={!input.trim()}
              >
                <FiSend />
                <span className="icon-tooltip" role="tooltip">
                  发送问题
                </span>
              </button>
            )}
          </div>
        </form>
        <div className="composer-footer">
          <FiShield aria-hidden="true" />
          <span>企业知识库</span>
          <span className="composer-footer-right">知库</span>
        </div>
      </div>
      {confirmClear && (
        <ConfirmDialog
          title="新建对话"
          description="当前对话记录将被清空，确定开始新对话？"
          confirmLabel="新建对话"
          busy={false}
          onClose={() => setConfirmClear(false)}
          onConfirm={() => {
            setMessages([]);
            setConfirmClear(false);
            setCopyError("");
            setCopied("");
          }}
        />
      )}
    </section>
  );
}
