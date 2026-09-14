"use client";
/**
 * SealBadge — §5.1 of the Design System
 * Double concentric ring SVG badge. Outer ring: brass-500, inner fill: verdict color at 12%.
 * Three sizes: 24 (inline list), 48 (scan detail header), 96 (challan — vector-safe).
 * Shape also varies per verdict for colorblind safety (§10 accessibility floor).
 */

export type VerdictStatus =
  | "PASSED"
  | "FAILED"
  | "PENDING_REVIEW"
  | "CALIBRATION_FAILED"
  | "QUEUED"
  | "PASS"
  | "FAIL"
  | "UNVERIFIED";

const VERDICT_CONFIG: Record<
  VerdictStatus,
  { color: string; fill: string; label: string; icon: string }
> = {
  PASSED: { color: "#1E7A4D", fill: "rgba(30,122,77,0.12)", label: "PASS", icon: "✓" },
  PASS:   { color: "#1E7A4D", fill: "rgba(30,122,77,0.12)", label: "PASS", icon: "✓" },
  FAILED: { color: "#B3261E", fill: "rgba(179,38,30,0.12)", label: "FAIL", icon: "✕" },
  FAIL:   { color: "#B3261E", fill: "rgba(179,38,30,0.12)", label: "FAIL", icon: "✕" },
  PENDING_REVIEW: {
    color: "#B5730B", // verdict-pending token
    fill: "rgba(181,115,11,0.12)",
    label: "REVIEW",
    icon: "◔",
  },
  UNVERIFIED: {
    color: "#B5730B",
    fill: "rgba(181,115,11,0.12)",
    label: "UNVERIFIED",
    icon: "◔",
  },
  CALIBRATION_FAILED: {
    color: "#6B7280",
    fill: "rgba(107,114,128,0.12)",
    label: "CAL. FAIL",
    icon: "?",
  },
  QUEUED: {
    color: "#6B7280",
    fill: "rgba(107,114,128,0.12)",
    label: "QUEUED",
    icon: "…",
  },
};

interface SealBadgeProps {
  verdict: VerdictStatus;
  size?: 24 | 48 | 96;
  /** suppress stamp animation (e.g. in list rows) */
  animate?: boolean;
  className?: string;
}

export function SealBadge({ verdict, size = 48, animate = false, className = "" }: SealBadgeProps) {
  const cfg = VERDICT_CONFIG[verdict] ?? VERDICT_CONFIG.QUEUED;
  const r = size / 2;
  const outerR = r - 1;
  const innerR = outerR - Math.max(2, size * 0.06);
  const fontSize = size === 24 ? 6 : size === 48 ? 11 : 20;

  return (
    <svg
      width={size}
      height={size}
      viewBox={`0 0 ${size} ${size}`}
      role="img"
      aria-label={cfg.label}
      className={`${animate ? "seal-stamp-anim" : ""} ${className} flex-shrink-0`}
      style={{ display: "inline-block" }}
    >
      {/* Outer ring — brass-500 */}
      <circle cx={r} cy={r} r={outerR} fill="none" stroke="#A6742C" strokeWidth={1} />
      {/* Inner fill — verdict color at 12% opacity */}
      <circle cx={r} cy={r} r={innerR} fill={cfg.fill} />
      {/* Inner ring — verdict color */}
      <circle cx={r} cy={r} r={innerR} fill="none" stroke={cfg.color} strokeWidth={0.8} />
      {/* Icon */}
      <text
        x={r}
        y={r + fontSize * 0.38}
        textAnchor="middle"
        fontSize={fontSize}
        fontWeight="600"
        fill={cfg.color}
        fontFamily="IBM Plex Mono, monospace"
        letterSpacing="0"
      >
        {cfg.icon}
      </text>
    </svg>
  );
}

/** Flat text-only chip variant for label rows */
export function VerdictChip({ verdict }: { verdict: VerdictStatus }) {
  const cfg = VERDICT_CONFIG[verdict] ?? VERDICT_CONFIG.QUEUED;
  return (
    <span
      className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-mono font-semibold"
      style={{ color: cfg.color, backgroundColor: cfg.fill, border: `1px solid ${cfg.color}40` }}
    >
      {cfg.icon} {cfg.label}
    </span>
  );
}
