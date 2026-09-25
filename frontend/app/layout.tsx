import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Haber Analiz",
  description: "Yunan ve İsrail basınında Türkiye",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="tr">
      <body>
        <header className="site-header">
          <div className="container header-row">
            <Link href="/" className="brand">Haber Analiz</Link>
            <span className="tagline">Yunan ve İsrail basınında Türkiye</span>
          </div>
        </header>
        <main className="container">{children}</main>
        <footer className="site-footer container">
          Haberler kaynaklarından özetlenerek Türkçe olarak yeniden yazılmıştır. Tam metin için her haberdeki kaynak bağlantısını kullanın.
        </footer>
      </body>
    </html>
  );
}
