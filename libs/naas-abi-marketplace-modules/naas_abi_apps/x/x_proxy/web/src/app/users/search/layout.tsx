import type { Metadata } from "next";

/** Named here rather than in `page.tsx`: that is a client component. */
export const metadata: Metadata = { title: "Search Users" };

export default function SearchUsersLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
