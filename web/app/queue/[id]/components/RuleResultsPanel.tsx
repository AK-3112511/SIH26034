"use client";
import { AlertTriangle, CheckCircle2, FileCheck2, XCircle } from "lucide-react";
import { VerdictChip, type VerdictStatus } from "@/app/components/SealBadge";
import type { RuleResult } from "@/lib/api";
import { ruleMeta } from "./rules";

interface RuleResultsPanelProps {
  results: RuleResult[];
  rulesetVersion: string | null;
}

/** Per-rule outcome, read straight from the engine and never recomputed here. */
export function RuleResultsPanel({ results, rulesetVersion }: RuleResultsPanelProps) {
  return (
    <section className="space-y-3" aria-labelledby="rules-heading">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <FileCheck2 size={16} className="text-brass-500" aria-hidden />
          <h2
            id="rules-heading"
            className="font-display text-sm font-semibold uppercase tracking-wider text-ink-900"
          >
            Statutory rule results
          </h2>
        </div>
        <span className="font-mono text-xs text-ink-600">
          Ruleset {rulesetVersion ?? "not recorded"}
        </span>
      </div>

      <div className="card-surface overflow-hidden p-0">
        {results.length === 0 ? (
          <p className="p-4 font-body text-xs text-ink-600">
            No rules have been evaluated for this scan yet.
          </p>
        ) : (
          <ul className="divide-y divide-ink-900/10">
            {results.map((rule) => {
              const meta = ruleMeta(rule.rule_id);
              return (
                <li key={rule.id} className="p-3.5">
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-start gap-2.5">
                      {rule.status === "PASS" && (
                        <CheckCircle2 size={18} className="mt-0.5 shrink-0 text-verdict-pass" aria-hidden />
                      )}
                      {rule.status === "FAIL" && (
                        <XCircle size={18} className="mt-0.5 shrink-0 text-verdict-fail" aria-hidden />
                      )}
                      {rule.status === "UNVERIFIED" && (
                        <AlertTriangle size={18} className="mt-0.5 shrink-0 text-verdict-pending" aria-hidden />
                      )}
                      <div>
                        <span className="block font-body text-sm font-semibold text-ink-900">
                          {meta.section} &mdash; {meta.label}
                        </span>
                        <span className="mt-0.5 block font-body text-xs text-ink-600">
                          {meta.desc}
                        </span>
                      </div>
                    </div>
                    <VerdictChip verdict={rule.status as VerdictStatus} />
                  </div>

                  {rule.reason && (
                    <div className="ml-7 mt-2.5 rounded bg-ink-900/5 p-2 font-body text-xs text-ink-900">
                      <span className="block text-[10px] font-semibold uppercase text-ink-600">
                        Finding
                      </span>
                      <span className="mt-0.5 block">{rule.reason}</span>
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </section>
  );
}
