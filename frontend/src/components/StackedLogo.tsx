export default function StackedLogo({
  size = 16,
  color = "currentColor",
}: {
  size?: number;
  color?: string;
}) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <rect x="3" y="1.5" width="10" height="3.5" rx="0.5" fill={color} />
      <rect x="4.5" y="6.5" width="10" height="3.5" rx="0.5" fill={color} />
      <rect x="2" y="11.5" width="10" height="3.5" rx="0.5" fill={color} />
    </svg>
  );
}
