import { useEffect, useState } from "react";
import { getModels, type ModelInfo } from "../api";

const FALLBACK: ModelInfo[] = [{ id: "auto", label: "자동", provider: "auto" }];

/** GET /models once after login. "자동" is always first, also when the call fails. */
export function useModels(enabled: boolean): ModelInfo[] {
  const [models, setModels] = useState<ModelInfo[]>(FALLBACK);
  useEffect(() => {
    if (!enabled) return;
    getModels()
      .then((d) => setModels(d.models.length ? d.models : FALLBACK))
      .catch(() => setModels(FALLBACK));
  }, [enabled]);
  return models;
}
