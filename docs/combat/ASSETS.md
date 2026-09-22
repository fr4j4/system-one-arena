# Recursos y procedencia

Las mallas, escenarios y efectos de combate fueron creados para este repositorio. Esta rama experimental incorpora además animaciones CC0 de Quaternius; ver [QUATERNIUS.md](QUATERNIUS.md). No incluye personajes, música, logotipos ni recursos extraídos de Mortal Kombat o Dragon Ball.

| Recurso | Fuente | Licencia / uso |
|---|---|---|
| Ember, Flux, Terra, Nyx GLB | `scripts/build_fighters.py` | Original del proyecto; CC0-1.0 para estos archivos generados |
| 18 huesos / 25 animaciones por personaje | Mismo generador; curvas originales | CC0-1.0 |
| Santuario y Reactor Celeste | `frontend/src/combat/stage.ts` | Código original del proyecto |
| Poderes, auras, partículas y remates | `Scene.tsx`, `powers.ts` | Código original del proyecto |
| Efectos y música | Síntesis Web Audio en `audio.ts` | Composiciones originales, sin samples externos |
| Barlow Condensed, DM Sans, IBM Plex Mono | Paquetes `@fontsource/*` fijados en package-lock | SIL Open Font License; licencias incluidas en paquetes |
| Iconos de interfaz | lucide-react | ISC |
| Clips Quaternius Standard | Fuente GLB conservada en `assets/sources/quaternius/`, conversión offline | CC0-1.0; licencia incluida |
| Renderizador | Three.js | MIT |

Los GLB son archivos binarios glTF2 con skin, inverse bind matrices y clips quaternion. No requieren CDN ni recursos externos. Cuatro archivos, aproximadamente 0.74 MB cada uno; se precargan sólo los personajes seleccionados, con caché de assets. El generador es determinista y no necesita Blender ni descargas.

Reconstruir: `.venv/bin/python scripts/build_fighters.py`. Las geometrías, materiales, shadow maps, mezcladores, RAF y listeners se liberan al desmontar la escena; partículas limitadas según calidad. La base del GLB permanece en caché para reutilización de CPU.
