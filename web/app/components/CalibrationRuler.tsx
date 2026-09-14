/**
 * CalibrationRuler — §1 + §4 signature structural divider.
 * A 2px rule with millimeter-style SVG tick marks every 8px (the base spacing unit).
 * brass-500 color. Used at every major section boundary — never decorative.
 */

interface CalibrationRulerProps {
  className?: string;
}

export function CalibrationRuler({ className = "" }: CalibrationRulerProps) {
  // 1440px max content width; render enough ticks for full width
  const width = 1440;
  const tickInterval = 8;  // 8px == 1 grid unit == 1 "mm" on the ruler
  const tallTickEvery = 5; // every 5th tick is tall (major division)
  const shortH = 4;
  const tallH = 8;

  const ticks: React.ReactNode[] = [];
  for (let x = 0; x <= width; x += tickInterval) {
    const isMajor = (x / tickInterval) % tallTickEvery === 0;
    const h = isMajor ? tallH : shortH;
    ticks.push(
      <line
        key={x}
        x1={x}
        y1={0}
        x2={x}
        y2={h}
        stroke="#A6742C"
        strokeWidth={isMajor ? 1.2 : 0.8}
        strokeLinecap="round"
      />
    );
  }

  return (
    <div
      className={`w-full overflow-hidden ${className}`}
      aria-hidden="true"
      role="presentation"
    >
      <svg
        width="100%"
        height="10"
        viewBox={`0 0 ${width} 10`}
        preserveAspectRatio="xMinYMid meet"
        style={{ display: "block" }}
      >
        {/* Base line */}
        <line x1={0} y1={2} x2={width} y2={2} stroke="#A6742C" strokeWidth={2} />
        {/* Tick marks below the line */}
        {ticks}
      </svg>
    </div>
  );
}
