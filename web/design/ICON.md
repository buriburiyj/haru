# Changing the app icon
1. Put the new square picture (full-bleed, no transparent corners, 1024x1024 is best) at `web/design/icon-source.png`, replacing the old one.
2. Run `cd web && npm run icons` (add `MASK_BG=RRGGBB` with the picture's edge color for the Android maskable icon); it rewrites `public/icons/*` and `src/assets/logo.png`.
3. Commit those generated files with the new source. Do not touch `tokens.css`: the accent color stays #DA7756. Logo.tsx, index.html and manifest.webmanifest only point at the generated files.
