import type { ReactNode } from "react";
import Logo from "./Logo";

function greeting(h: number): string {
  if (h >= 5 && h < 11) return "좋은 아침입니다";
  if (h >= 11 && h < 17) return "안녕하세요";
  if (h >= 17 && h < 22) return "좋은 저녁입니다";
  return "늦은 시간이네요";
}

// `children` is the <Composer/> element.
export default function Welcome({ children }: { children: ReactNode }) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-6 px-4">
      <div className="flex items-center gap-3">
        <Logo />
        <h1 className="text-3xl text-fg">{greeting(new Date().getHours())}</h1>
      </div>
      {children}
    </div>
  );
}
