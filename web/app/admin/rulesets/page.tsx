"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { ComingSoon } from "@/app/components/ComingSoon";
import { useAuth } from "@/lib/auth-context";

export default function AdminRulesetsPage() {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && user && user.role !== "admin") {
      router.replace("/");
    }
  }, [loading, user, router]);

  if (loading || !user) {
    return (
      <div className="min-h-screen bg-paper-100 flex items-center justify-center">
        <span className="font-mono text-sm text-ink-600">Verifying credentials…</span>
      </div>
    );
  }

  if (user.role !== "admin") {
    return (
      <div className="min-h-screen bg-paper-100 flex items-center justify-center">
        <span className="font-mono text-sm text-ink-600">Admin access required…</span>
      </div>
    );
  }

  return (
    <ComingSoon
      title="Ruleset Configuration"
      phase="Phase 6.3"
      description="Versioned Schedule II editor. Save as a new version only — never overwrite a version referenced by a past challan."
    />
  );
}
