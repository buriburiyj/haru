import type { ReactNode } from "react";
import Logo from "./Logo";
import { TempChatBanner, TempChatToggle } from "./temp/TempChat";

function greeting(h: number): string {
  if (h >= 5 && h < 11) return "좋은 아침입니다";
  if (h >= 11 && h < 17) return "안녕하세요";
  if (h >= 17 && h < 22) return "좋은 저녁입니다";
  return "늦은 시간이네요";
}

// `children` is the <Composer/> element.
export default function Welcome({ children }: { children: ReactNode }) {
  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center px-3 py-2">
        <button
          type="button"
          onClick={() => window.dispatchEvent(new Event("haru:open-drawer"))}
          aria-label="메뉴"
          className="flex h-11 w-11 items-center justify-center rounded-lg text-fg hover:bg-surface-2 md:hidden"
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
            <path d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>
        <div className="ml-auto">
          <TempChatToggle />
        </div>
      </div>
      <TempChatBanner />
      <div className="flex min-h-0 flex-1 flex-col items-center justify-center gap-6 px-4">
        <div className="flex items-center gap-3">
          <Logo />
          <h1 className="text-3xl text-fg">{greeting(new Date().getHours())}</h1>
        </div>
        {children}
      </div>
    </div>
  );
}
