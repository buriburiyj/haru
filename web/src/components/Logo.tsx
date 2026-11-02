// 임시 로고: 주황 원 안에 ∞. 나중에 icon.png 로 교체합니다.
export default function Logo({ size = 40 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 40 40" role="img" aria-label="Haru">
      <circle cx="20" cy="20" r="20" fill="var(--haru-accent)" />
      <path
        d="M20 20c-2.2-3.4-4.4-5-7-5a5 5 0 0 0 0 10c2.6 0 4.8-1.600 7-5s4.400-5 7-5a5 5 0 0 1 0 10c-2.600 0-4.800-1.600-7-5Z"
        fill="none"
        stroke="var(--haru-accent-fg)"
        strokeWidth="2.400"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
