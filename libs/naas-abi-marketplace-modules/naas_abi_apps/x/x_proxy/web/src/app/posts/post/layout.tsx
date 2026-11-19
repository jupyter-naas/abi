import type { Metadata } from "next";

/** Named here rather than in `page.tsx`: that is a client component. */
export const metadata: Metadata = { title: "Post" };

export default function PostLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
