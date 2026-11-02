import { useEffect } from "react";

/**
 * Keeps the app exactly as tall as the visible area, so on iPhone the composer stays above the keyboard.
 * iOS shrinks the visual viewport (not the layout viewport) when the keyboard opens, so the #root height follows it.
 */
export function useVisualViewportHeight() {
  useEffect(() => {
    const vv = window.visualViewport;
    const root = document.getElementById("root");
    if (!vv || !root) return;
    const update = () => {
      root.style.height = `${vv.height}px`;
      // iOS may scroll the page to reveal the focused input; keep the app pinned to the top.
      if (window.scrollY !== 0) window.scrollTo(0, 0);
    };
    update();
    vv.addEventListener("resize", update);
    vv.addEventListener("scroll", update);
    return () => {
      vv.removeEventListener("resize", update);
      vv.removeEventListener("scroll", update);
      root.style.height = "";
    };
  }, []);
}
