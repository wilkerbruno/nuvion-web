import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Nuvion Web",
  description: "Painel de gestão do Nuvion Web",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR">
      <body>{children}</body>
    </html>
  );
}
