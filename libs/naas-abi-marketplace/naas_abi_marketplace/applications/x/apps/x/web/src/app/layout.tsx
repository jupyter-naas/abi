import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "X",
  description: "Recent tweets count and search dashboard",
  // Metadata icon URLs are not rewritten by basePath, so this is the full
  // served path: public/favicon.svg lands at the export root.
  icons: { icon: "/app-html/x/apps/x/favicon.svg" },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
