import { useEffect, useRef } from "react";
import { Button, Dialog } from "../ui";

/** Confirmation window. Every delete in the UI must go through this. Props only, no data access. */
export default function ConfirmDialog({
  title,
  message,
  confirmLabel = "삭제",
  danger = true,
  onConfirm,
  onCancel,
}: {
  title: string;
  message?: string;
  confirmLabel?: string;
  danger?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const cancelRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    cancelRef.current?.focus(); // the safe choice has focus, so Enter never deletes by accident
  }, []);
  return (
    <Dialog
      title={title}
      onClose={onCancel}
      className="md:max-w-sm"
      footer={
        <>
          <Button ref={cancelRef} onClick={onCancel}>
            취소
          </Button>
          <Button variant={danger ? "danger" : "primary"} onClick={onConfirm}>
            {confirmLabel}
          </Button>
        </>
      }
    >
      {message && <p className="text-sm text-muted">{message}</p>}
    </Dialog>
  );
}
