import type { Metadata } from "next";

/** Named here rather than in `page.tsx`: that is a client component. */
export const metadata: Metadata = { title: "Count Recent Tweets" };

export default function CountRecentPostsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
