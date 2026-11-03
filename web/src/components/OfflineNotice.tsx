import { useEffect, useState } from "react";

/** Shows a notice while the browser reports no network. No service worker: the screen only informs. */
export default function OfflineNotice() {
  const [online, setOnline] = useState(() => (typeof navigator === "undefined" ? true : navigator.onLine));
  useEffect(() => {
    const on = () => setOnline(true);
    const off = () => setOnline(false);
    window.addEventListener("online", on);
    window.addEventListener("offline", off);
    return () => {
      window.removeEventListener("online", on);
      window.removeEventListener("offline", off);
    };
  }, []);
  if (online) return null;
  return (
    <div
      role="status"
      className="fixed inset-x-0 top-0 z-[70] bg-danger px-4 py-2 text-center text-sm text-accent-fg"
      style={{ paddingTop: "calc(0.5rem + env(safe-area-inset-top))" }}
    >
      인터넷 연결이 없습니다
    </div>
  );
}
