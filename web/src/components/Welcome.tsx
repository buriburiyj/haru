import type { ReactNode } from "react";
import Logo from "./Logo";

// STUB - owner: sidebar/welcome agent. `children` is the <Composer/> element.
export default function Welcome({ children }: { children: ReactNode }) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-6 px-4">
      <Logo />
      <p>안녕하세요.</p>
      {children}
    </div>
  );
}
