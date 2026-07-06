"use client";

import React, { useState, useRef, useEffect } from "react";
import { askQuestion, streamQuestion } from "@/lib/api";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
  isStreaming?: boolean;
}

interface Source {
  index: number;
  doc_title: string;
  doc_id: string;
  chunk_id: string;
  page_number: number | null;
  score: number;
  excerpt: string;
}

export default function HomePage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [useStream, setUseStream] = useState(true);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || loading) return;

    const question = input.trim();
    setInput("");

    const userMsg: Message = {
      id: Date.now().toString(),
      role: "user",
      content: question,
    };

    const assistantMsg: Message = {
      id: (Date.now() + 1).toString(),
      role: "assistant",
      content: "",
      isStreaming: true,
    };

    setMessages((prev) => [...prev, userMsg, assistantMsg]);
    setLoading(true);

    try {
      if (useStream) {
        await streamQuestion(
          question,
          (sources) => {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMsg.id ? { ...m, sources } : m
              )
            );
          },
          (token) => {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMsg.id
                  ? { ...m, content: m.content + token }
                  : m
              )
            );
          },
          () => {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMsg.id ? { ...m, isStreaming: false } : m
              )
            );
          }
        );
      } else {
        const result = await askQuestion(question);
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantMsg.id
              ? {
                  ...m,
                  content: result.answer,
                  sources: result.sources,
                  isStreaming: false,
                }
              : m
          )
        );
      }
    } catch (err: any) {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantMsg.id
            ? {
                ...m,
                content: `抱歉，请求出错了：${err.message || "未知错误"}`,
                isStreaming: false,
              }
            : m
        )
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-8rem)] max-w-4xl mx-auto">
      {/* Header */}
      <div className="text-center mb-6">
        <h2 className="text-2xl font-bold text-gray-900 mb-2">
          企业知识库问答
        </h2>
        <p className="text-gray-500 text-sm">
          上传企业文档后，用自然语言提问，获取带来源引用的答案
        </p>
      </div>

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto mb-4 space-y-4 p-4 bg-white rounded-xl border border-gray-200 shadow-sm">
        {messages.length === 0 && (
          <div className="text-center text-gray-400 mt-20">
            <p className="text-5xl mb-4">🤖</p>
            <p className="text-lg">欢迎使用企业知识库助手</p>
            <p className="text-sm mt-2">
              你可以问企业制度、产品文档、FAQ 等相关问题
            </p>
            <div className="mt-6 flex flex-wrap gap-2 justify-center">
              {[
                "公司年假怎么申请？",
                "出差报销需要哪些材料？",
                "新员工入职流程是什么？",
              ].map((q) => (
                <button
                  key={q}
                  onClick={() => setInput(q)}
                  className="px-3 py-1.5 text-sm text-gray-600 bg-gray-100 rounded-full hover:bg-primary-50 hover:text-primary-700 transition-colors"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[80%] rounded-2xl px-4 py-3 ${
                msg.role === "user"
                  ? "bg-primary-600 text-white"
                  : "bg-gray-100 text-gray-900"
              }`}
            >
              {/* Message Content */}
              <div
                className={`prose-custom text-sm ${
                  msg.role === "user" ? "text-white" : "text-gray-900"
                }`}
              >
                {msg.content || (
                  <span className="inline-flex items-center gap-1 text-gray-400">
                    <span className="animate-pulse">●</span>
                    <span className="animate-pulse" style={{ animationDelay: "0.2s" }}>●</span>
                    <span className="animate-pulse" style={{ animationDelay: "0.4s" }}>●</span>
                  </span>
                )}
              </div>

              {/* Sources */}
              {msg.sources && msg.sources.length > 0 && !msg.isStreaming && (
                <div className="mt-3 pt-3 border-t border-gray-200">
                  <p className="text-xs font-semibold text-gray-500 mb-2">
                    📚 引用来源 ({msg.sources.length})
                  </p>
                  <div className="space-y-1.5">
                    {msg.sources.map((src) => (
                      <div
                        key={src.index}
                        className="text-xs text-gray-600 bg-white rounded-lg px-2.5 py-1.5 border border-gray-100"
                      >
                        <span className="font-medium text-primary-700">
                          [{src.index}]
                        </span>{" "}
                        <span className="font-medium">{src.doc_title}</span>
                        {src.page_number && (
                          <span> · 第{src.page_number}页</span>
                        )}
                        <span className="text-gray-400">
                          {" "}
                          · 相似度: {(src.score * 100).toFixed(1)}%
                        </span>
                        <p className="text-gray-500 mt-0.5 line-clamp-2">
                          {src.excerpt}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <form onSubmit={handleSubmit} className="flex gap-3">
        <div className="flex-1 relative">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="输入你的问题，例如：年假怎么申请？"
            className="w-full px-4 py-3 pr-12 border border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent text-sm"
            disabled={loading}
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="absolute right-2 top-1/2 -translate-y-1/2 w-8 h-8 bg-primary-600 text-white rounded-lg flex items-center justify-center disabled:opacity-50 disabled:cursor-not-allowed hover:bg-primary-700 transition-colors"
          >
            {loading ? (
              <span className="animate-spin text-xs">⏳</span>
            ) : (
              <span className="text-xs">↑</span>
            )}
          </button>
        </div>
      </form>

      {/* Options */}
      <div className="flex items-center justify-between mt-2 text-xs text-gray-400">
        <label className="flex items-center gap-1.5 cursor-pointer">
          <input
            type="checkbox"
            checked={useStream}
            onChange={(e) => setUseStream(e.target.checked)}
            className="rounded border-gray-300 text-primary-600 focus:ring-primary-500"
          />
          流式输出
        </label>
        <span>基于 OpenAI Responses API + pgvector</span>
      </div>
    </div>
  );
}
