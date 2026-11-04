import { useEffect, useState } from "react";

// Small toast shown after copying (listens to the "haru:copied" event fired by copyText).
export default function CopyToast() {
  const [show, setShow] = useState(false);
  useEffect(() => {
    let t: ReturnType<typeof setTimeout>;
    const on = () => {
      setShow(true);
      clearTimeout(t);
      t = setTimeout(() => setShow(false), 1500);
    };
    window.addEventListener("haru:copied", on);
    return () => {
      window.removeEventListener("haru:copied", on);
      clearTimeout(t);
    };
  }, []);
  return (
    <div
      role="status"
      className={
        "pointer-events-none fixed bottom-24 left-1/2 z-50 -translate-x-1/2 rounded-pill border border-line bg-surface px-4 py-2 text-sm text-fg shadow-pop transition-opacity " +
        (show ? "opacity-100" : "opacity-0")
      }
    >
      복사했습니다
    </div>
  );
}
