import { useEffect, useState } from "react";
import SettingsDialog from "./settings/SettingsDialog";
import SearchDialog from "./search/SearchDialog";

export default function Overlays({ isMacApp = false }: { isMacApp?: boolean }) {
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (!(e.metaKey || e.ctrlKey) || e.altKey || e.shiftKey) return;
      if (e.key === ",") {
        e.preventDefault();
        setSearchOpen(false);
        setSettingsOpen(true);
      } else if (e.key.toLowerCase() === "k") {
        e.preventDefault();
        setSettingsOpen(false);
        setSearchOpen(true);
      }
    };
    const openSettings = () => {
      setSearchOpen(false);
      setSettingsOpen(true);
    };
    const openSearch = () => {
      setSettingsOpen(false);
      setSearchOpen(true);
    };
    window.addEventListener("keydown", onKey);
    window.addEventListener("haru:open-settings", openSettings);
    window.addEventListener("haru:open-search", openSearch);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("haru:open-settings", openSettings);
      window.removeEventListener("haru:open-search", openSearch);
    };
  }, []);

  return (
    <>
      {settingsOpen && <SettingsDialog isMacApp={isMacApp} onClose={() => setSettingsOpen(false)} />}
      {searchOpen && <SearchDialog onClose={() => setSearchOpen(false)} />}
    </>
  );
}
