"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { landingHref } from "@/lib/routes";

/**
 * The app root forwards to the default page.
 *
 * Every view has a path of its own, so `/` holds none of them; it exists as the
 * entry point Nexus and older links point at, and forwards without adding a
 * history entry. Links minted before the pages had paths (`?page=users&
 * user=grok`) are translated on the way through.
 */
export default function Home() {
  const router = useRouter();

  useEffect(() => {
    router.replace(landingHref(window.location.search));
  }, [router]);

  return <div className="status">Loading…</div>;
}
