import logoUrl from "../assets/logo.png";

// logo.png is made by `npm run icons` from web/design/icon-source.png (see web/design/ICON.md). Do not edit it by hand.
export default function Logo({ size = 40 }: { size?: number }) {
  return <img src={logoUrl} width={size} height={size} alt="Haru" className="rounded-icon" style={{ objectFit: "contain" }} />;
}
