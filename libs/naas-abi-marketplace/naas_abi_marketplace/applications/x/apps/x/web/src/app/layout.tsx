import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "X · Recent Tweets",
  description: "Recent tweets count and search dashboard",
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
