import type { Metadata } from "next";
import { AppProvider } from "@/components/AppProvider";
import "./globals.css";

export const metadata: Metadata = {
  title: "X - Tweets Hub",
  description: "Tweets hub — counts, search, and authors",
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
      <body>
        {/* Mounted once and kept across page changes — see AppProvider. */}
        <AppProvider>{children}</AppProvider>
      </body>
    </html>
  );
}
