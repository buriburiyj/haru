import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import UiDemo from "./components/ui/UiDemo";
import WorkDemo from "./components/work/WorkDemo";
import "./index.css";

const demo = new URLSearchParams(window.location.search).get("demo");

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    {demo === "ui" ? <UiDemo /> : demo === "work" ? <WorkDemo /> : <App />}
  </StrictMode>,
);

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register(`${import.meta.env.BASE_URL}sw.js`).catch(() => {});
  });
}
