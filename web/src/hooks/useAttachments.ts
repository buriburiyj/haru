import { useCallback, useEffect, useRef, useState } from "react";
import { HttpError, uploadImage } from "../api";
import type { Attachment } from "../components/chat/dataTypes";

const MAX_BYTES = 3 * 1024 * 1024; // server limit: 3 MB
const MAX_COUNT = 3; // the server reads at most 3 photos per request

/** Photos chosen in the composer: validates, uploads right away, keeps previews. */
export function useAttachments(onUnauthorized: () => void) {
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const [notice, setNotice] = useState("");
  const live = useRef<Attachment[]>([]);
  live.current = attachments;

  const patch = (key: string, p: Partial<Attachment>) =>
    setAttachments((a) => a.map((x) => (x.key === key ? { ...x, ...p } : x)));

  const add = useCallback(
    (files: File[]) => {
      setNotice("");
      for (const file of files) {
        if (live.current.length >= MAX_COUNT) {
          setNotice("사진은 한 번에 3장까지 보낼 수 있습니다.");
          break;
        }
        if (!file.type.startsWith("image/")) {
          setNotice("사진 파일만 올릴 수 있습니다.");
          continue;
        }
        if (file.size > MAX_BYTES) {
          setNotice("사진은 3MB까지 올릴 수 있습니다. 더 작은 사진을 골라 주세요.");
          continue;
        }
        const key = `${Date.now()}-${Math.random().toString(36).slice(2)}`;
        const item: Attachment = { key, name: file.name, previewUrl: URL.createObjectURL(file), status: "uploading" };
        live.current = [...live.current, item];
        setAttachments(live.current);
        uploadImage(file, file.name)
          .then((u) => patch(key, { id: u.id, status: "ready" }))
          .catch((err) => {
            if ((err as Error).message === "unauthorized") return onUnauthorized();
            const s = err instanceof HttpError ? err.status : 0;
            const error =
              s === 413
                ? "사진은 3MB까지 올릴 수 있습니다."
                : s === 415
                  ? "jpeg, png, webp, gif 사진만 올릴 수 있습니다."
                  : s === 502
                    ? "사진을 저장하지 못했습니다. 잠시 뒤에 다시 시도해 주세요."
                    : "사진을 올리지 못했습니다.";
            patch(key, { status: "error", error });
            setNotice(error);
          });
      }
    },
    [onUnauthorized],
  );

  const remove = useCallback((key: string) => {
    setAttachments((a) => {
      const x = a.find((i) => i.key === key);
      if (x) URL.revokeObjectURL(x.previewUrl);
      return a.filter((i) => i.key !== key);
    });
    setNotice("");
  }, []);

  /** Call after the message was sent. */
  const clear = useCallback(() => {
    live.current.forEach((x) => URL.revokeObjectURL(x.previewUrl));
    setAttachments([]);
    setNotice("");
  }, []);

  useEffect(() => () => live.current.forEach((x) => URL.revokeObjectURL(x.previewUrl)), []);

  const uploading = attachments.some((a) => a.status === "uploading");
  const readyIds = attachments.filter((a) => a.status === "ready" && a.id).map((a) => a.id as string);

  return { attachments, notice, uploading, readyIds, add, remove, clear };
}
