import type { Metadata } from "next";

/** Named here rather than in `page.tsx`: that is a client component. */
export const metadata: Metadata = { title: "Parameters" };

export default function ParametersLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
