import type { Metadata, Viewport } from "next";
import { AppProvider } from "@/components/AppProvider";
import "./globals.css";

export const metadata: Metadata = {
  // Each page names itself in its own `layout.tsx`; the template puts the app
  // in front of it, so a tab reads "X Proxy | Search Users".
  title: { default: "X Proxy", template: "X Proxy | %s" },
  description: "X proxy - post counts, post search, and authors",
  // Metadata icon URLs are not rewritten by basePath, so this is the full
  // served path: public/favicon.svg lands at the export root.
  icons: { icon: "/app-html/x/apps/x_proxy/favicon.svg" },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        {/* Mounted once and kept across page changes - see AppProvider. */}
        <AppProvider>{children}</AppProvider>
      </body>
    </html>
  );
}
