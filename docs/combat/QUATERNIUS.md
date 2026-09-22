# Prueba de animaciones Quaternius

Rama: `feat/quaternius-animations`. La rama main conserva la versión anterior.

## Probar

- Arena: `http://localhost:8014/` (Quaternius por defecto en esta rama).
- Comparación lado a lado: `http://localhost:8014/?animation-lab`.
- Arena con curvas originales: `http://localhost:8014/?animations=original`.

El visor permite elegir cualquiera de los cuatro personajes, elegir los 25 movimientos, pausar, desplazar el progreso y girar la cámara. Compara el mismo progreso normalizado; las duraciones originales pueden diferir. No crea partidas ni consulta modelos.

## Procedencia y cobertura

[Universal Animation Library Standard de Quaternius](https://quaternius.itch.io/universal-animation-library), descargada el 22-09-2026 desde la descarga gratuita oficial. Licencia CC0-1.0 incluida en `assets/sources/quaternius/LICENSE.txt`. Se conserva el GLB Standard sin root motion como entrada reproducible (7.6 MB); el navegador sólo descarga la conversión de aproximadamente 0.7 MB una vez por sesión de página, compartida entre ambos jugadores. No necesita CDN ni servicios externos.

| Arena | Clip Standard |
|---|---|
| idle | Idle_Loop |
| walk | Walk_Loop |
| dash_forward / dash_back | Jog_Fwd_Loop |
| jump | Jump_Loop |
| light | Punch_Jab |
| heavy | Punch_Cross |
| hurt | Hit_Chest |
| charge | Spell_Simple_Idle_Loop |
| bolt | Spell_Simple_Shoot |

La edición gratuita contiene 43 clips. Se importan 10 acciones (9 clips fuente distintos). Guardias, patadas, evasión, derribo, técnicas especiales, victoria y remate conservan las curvas originales. No se afirma que el paquete incluya todas las técnicas de lucha. Los desplazamientos hacia atrás reutilizan locomoción hacia delante; es una limitación de esta primera prueba.

## Adaptación

`frontend/scripts/build-quaternius.mjs` carga ambos rigs con GLTFLoader. Mapea huesos anatómicos, convierte rotaciones globales a la jerarquía original y corrige las direcciones T-pose → A-pose. Los huesos intermedios no presentes (clavículas/columna adicional) contribuyen a las rotaciones globales. Las manos heredan la corrección del antebrazo. No se cambian mallas, materiales, proporciones ni pesos de los personajes.

Se muestrea a 30 Hz con interpolación quaternion en Three.js. Identificadores de clip únicos y deterministas evitan colisiones en AnimationMixer. Sólo se importa la oscilación vertical local de la pelvis escalada a las piernas; se descartan traslación horizontal y altura de salto. El servidor sigue controlando posición, orientación, salto, daño, energía y ventanas de ataque. Los golpes se reproducen según el progreso de `move_timing` del servidor; la máxima extensión del jab/cross se encuentra cerca del inicio activo actual. No se generan impactos desde eventos de animación.

Los clips se cargan en paralelo al personaje y sustituyen sólo los nombres mapeados. Un fallo de descarga es visible y reintentable, no se oculta con un fallback silencioso. Las animaciones exclusivas permanecen disponibles. `?animations=original` evita la descarga de Quaternius.

## Reconstrucción y verificación

Desde `frontend` después de `npm ci`:

```sh
node scripts/build-quaternius.mjs
node scripts/check-quaternius.mjs
npm run build
npm run test:e2e
```

La comprobación offline verifica 440 poses: tracks válidos, huesos existentes, rotaciones normalizadas, posiciones acotadas, ausencia de root motion/XZ, IDs distintos y extensión de cada puñetazo. La prueba de navegador cubre carga única de clips, selección de cuatro personajes, pausa/scrubbing, conservación de técnicas originales y ausencia de consultas a modelos en el visor.

Para levantar esta rama en otro checkout (puerto independiente):

```sh
PYTHONPATH=backend ARENA_FRONTEND_DIR="$PWD/frontend/dist" \
COMBAT_DATA_DIR=/tmp/eclipse-quaternius \
.venv/bin/uvicorn arena.app:app --host 0.0.0.0 --port 8014
```

Las credenciales continúan siendo configuración local `.env`, excluida de Git. La rama no modifica el protocolo de los modelos.

## Resultado verificado (22-09-2026)

- Build TypeScript/Vite correcto (aviso existente de tamaño del chunk Three.js).
- 74 pruebas backend y 7 pruebas Playwright aprobadas.
- 440 poses verificadas en los cuatro rigs, incluyendo extensión de jab/cross.
- Generación repetida produce el mismo SHA-256 del JSON.
- Inspección visual en Chromium: reposo, caminar, jab, cross y carga; sin errores JavaScript. La validación visual usa renderizado de software y no constituye una medición de FPS en GPU.
