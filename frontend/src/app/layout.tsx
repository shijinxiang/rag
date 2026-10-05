import type { Metadata } from "next";
import "./globals.css";
import Workspace from "@/components/workspace";


export const metadata: Metadata = {
  title: "Enterprise Knowledge RAG Agent",
  description: "企业知识库检索与问答智能体",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-CN">
      <body className="bg-gray-50 min-h-screen">
        {/* Top Navigation */}
        <nav className="bg-white border-b border-gray-200 sticky top-0 z-50">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex flex-wrap items-center justify-between gap-3 min-h-16 py-3">
              <div className="flex min-w-0 flex-1 items-center space-x-3">
                <div className="w-8 h-8 shrink-0 bg-primary-600 rounded-lg flex items-center justify-center">
                  <span className="text-white font-bold text-sm">RAG</span>
                </div>
                <div className="min-w-0">
                  <h1 className="text-base sm:text-lg font-semibold text-gray-900 break-words">
                    Enterprise Knowledge RAG Agent
                  </h1>
                  <p className="text-xs text-gray-500">企业知识库检索与问答智能体</p>
                </div>
              </div>
              <div className="flex shrink-0 items-center gap-3">
                <a
                  href="/docs"
                  className="text-sm text-gray-600 hover:text-gray-900"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  API 文档
                </a>
                <span className="px-3 py-1 bg-green-100 text-green-800 text-xs rounded-full font-medium">
                  v1.0
                </span>
              </div>
            </div>
          </div>
        </nav>

        {/* Main Content */}
        <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <Workspace>{children}</Workspace>
        </main>
      </body>
    </html>
  );
}
