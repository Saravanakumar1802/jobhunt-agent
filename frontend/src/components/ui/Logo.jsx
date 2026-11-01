/** The mark is three stacked job cards; the front one (blue) is the match. `busy` animates it. */
export function Mark({ size = 32, busy = false, className = "" }) {
  return (
    <span className={`relative inline-grid shrink-0 place-items-center ${className}`} style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox="0 0 64 64" aria-hidden>
        <rect width="64" height="64" rx="18" fill="#0b0e14" />
        <rect x="14" y="14" width="30" height="20" rx="5" fill="none" stroke="#697186" strokeWidth="3" />
        <rect x="18" y="22" width="30" height="20" rx="5" fill="#0b0e14" stroke="#9aabff" strokeWidth="3" />
        <g className={busy ? "breathe" : ""} style={{ transformOrigin: "37px 40px" }}>
          <rect x="22" y="30" width="30" height="20" rx="5" fill="#2747f5" />
          <circle cx="45" cy="40" r="3.5" fill="#d9f57e" />
        </g>
      </svg>
      {busy && (
        <svg className="orbit absolute -inset-1.5" viewBox="0 0 44 44" aria-hidden>
          <circle cx="22" cy="22" r="20.5" fill="none" stroke="#2747f5" strokeWidth="2" strokeDasharray="22 108" strokeLinecap="round" />
        </svg>
      )}
    </span>
  );
}

export default function Logo({ className = "" }) {
  return (
    <span className={`inline-flex items-center gap-2.5 ${className}`}>
      <Mark size={30} />
      <span className="font-semiwide whitespace-nowrap text-[1.05rem] font-bold max-[400px]:sr-only">Job Hunt Copilot</span>
    </span>
  );
}
