import "@fontsource/barlow-condensed/latin-500.css";
import "@fontsource/barlow-condensed/latin-600.css";
import "@fontsource/barlow-condensed/latin-700.css";
import "@fontsource/dm-sans/latin-400.css";
import "@fontsource/dm-sans/latin-500.css";
import "@fontsource/dm-sans/latin-600.css";
import "@fontsource/dm-sans/latin-700.css";
import "@fontsource/ibm-plex-mono/latin-400.css";
import "@fontsource/ibm-plex-mono/latin-500.css";
import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./style.css";
if (new URLSearchParams(location.search).has("animation-lab")) {
  import("./combat/animationLab").then(({ mountAnimationLab }) =>
    mountAnimationLab(document.getElementById("root")!),
  );
} else
  createRoot(document.getElementById("root")!).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>,
  );
