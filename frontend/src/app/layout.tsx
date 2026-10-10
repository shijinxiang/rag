import type { Metadata } from "next";
import "./globals.css";
import Workspace from "@/components/workspace";

export const metadata: Metadata = {
  title: "知库 · 企业知识工作台",
  description: "企业知识库检索与问答智能体",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-CN">
      <body>
        <Workspace>{children}</Workspace>
      </body>
    </html>
  );
}
