import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import UiDemo from "./components/ui/UiDemo";
import "./index.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    {new URLSearchParams(window.location.search).get("demo") === "ui" ? <UiDemo /> : <App />}
  </StrictMode>,
);

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register(`${import.meta.env.BASE_URL}sw.js`).catch(() => {});
  });
}
