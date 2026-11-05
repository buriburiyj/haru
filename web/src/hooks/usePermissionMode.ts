import { useCallback, useState } from "react";
import { MODE_ORDER, type PermissionMode } from "../work/types";

const KEY = "haru.permissionMode";

function read(): PermissionMode {
  try {
    const v = localStorage.getItem(KEY);
    return (MODE_ORDER as string[]).includes(v ?? "") ? (v as PermissionMode) : "auto";
  } catch {
    return "auto"; // storage can be blocked; the choice then lasts only for this session
  }
}

/** The chosen permission mode, remembered in localStorage. Default: auto. */
export function usePermissionMode(): [PermissionMode, (m: PermissionMode) => void] {
  const [mode, setModeState] = useState<PermissionMode>(read);
  const setMode = useCallback((m: PermissionMode) => {
    setModeState(m);
    try {
      localStorage.setItem(KEY, m);
    } catch {
      /* ignore */
    }
  }, []);
  return [mode, setMode];
}
