import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

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
      <body className={`${inter.className} bg-gray-50 min-h-screen`}>
        {/* Top Navigation */}
        <nav className="bg-white border-b border-gray-200 sticky top-0 z-50">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex justify-between h-16">
              <div className="flex items-center space-x-3">
                <div className="w-8 h-8 bg-primary-600 rounded-lg flex items-center justify-center">
                  <span className="text-white font-bold text-sm">RAG</span>
                </div>
                <div>
                  <h1 className="text-lg font-semibold text-gray-900">
                    Enterprise Knowledge RAG Agent
                  </h1>
                  <p className="text-xs text-gray-500">企业知识库检索与问答智能体</p>
                </div>
              </div>
              <div className="flex items-center space-x-4">
                <a
                  href="/docs"
                  className="text-sm text-gray-600 hover:text-gray-900"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  API 文档
                </a>
                <span className="px-3 py-1 bg-green-100 text-green-800 text-xs rounded-full font-medium">
                  MVP v1.0
                </span>
              </div>
            </div>
          </div>
        </nav>

        {/* Main Content */}
        <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          {children}
        </main>
      </body>
    </html>
  );
}
