import { useEffect, useRef, useState } from "react";
import { Chip, Menu, MenuDivider, MenuItem, ShieldIcon } from "../ui";
import { MODE_HINT, MODE_LABEL, MODE_ORDER, type PermissionMode } from "../../work/types";

const NOT_ISOLATED_HINT = "격리된 컴퓨터에서만 쓸 수 있습니다. 지금 컴퓨터에서는 사용할 수 없습니다";

/** Permission mode dropdown under the input. The menu opens above the chip. */
export default function PermissionModeMenu({
  mode,
  onChange,
  isolated,
}: {
  mode: PermissionMode;
  onChange: (m: PermissionMode) => void;
  isolated: boolean;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div ref={ref} className="relative inline-block">
      <Chip caret icon={<ShieldIcon size={16} />} aria-expanded={open} onClick={() => setOpen((v) => !v)}>
        {MODE_LABEL[mode]}
      </Chip>
      {open && (
        <Menu className="absolute bottom-full left-0 z-50 mb-1 w-80">
          {MODE_ORDER.map((m) => {
            const blocked = m === "all" && !isolated;
            return (
              <MenuItem
                key={m}
                check={m === mode}
                hint={blocked ? NOT_ISOLATED_HINT : MODE_HINT[m]}
            hintWrap
                disabled={blocked}
                className="disabled:opacity-50"
                onClick={() => {
                  if (blocked) return;
                  onChange(m);
                  setOpen(false);
                }}
              >
                {MODE_LABEL[m]}
              </MenuItem>
            );
          })}
          <MenuDivider />
          <p className="px-3 py-2 text-xs text-muted">
            큰 삭제, 밖으로 보내기(메시지·이메일·push·배포), 결제는 어느 모드에서도 멈추고 물어봅니다.
          </p>
        </Menu>
      )}
    </div>
  );
}
