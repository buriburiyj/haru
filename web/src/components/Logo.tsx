import logoUrl from "../assets/logo.png";

// Transparent-background logo from web/design/icon_transparent.png (native size ~194px; do not render larger).
export default function Logo({ size = 40 }: { size?: number }) {
  return <img src={logoUrl} width={size} height={size} alt="Haru" style={{ objectFit: "contain" }} />;
}
