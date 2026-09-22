# Verificación · Eclipse Arena

Ejecutado localmente el 2026-09-22. Evidencia de proveedores en `docs/combat/evidence/`. Estas cifras corresponden a este equipo y a las peticiones de prueba, no a garantías del proveedor.

## Motor, API y navegador

- 74 pruebas de Python aprobadas: reglas, recursos, cancelaciones, cuerpos, combos, proyectiles, guardia/parry, choques sellados, remates, presets, replay determinista, fases, concurrencia, plazos, pausa/stop, perfiles, series, protocolo, persistencia y GLB originales.
- Ruff check y format sin errores; frontend TypeScript + Vite compilado y Prettier verificado.
- Seis pruebas de navegador aprobadas: selección independiente de slots; decisiones y pausa/stop sin nuevas llamadas; teclado y pérdida de foco; reasignación; choque y remate; series emparejadas y replay; móvil sin overflow. Control de mando probado con Gamepad API simulada, no con hardware físico.
- El bug de fin de remate se corrigió notificando estado final antes de esperar cierre de procesos/llamadas, y evitando que una respuesta HTTP antigua reabra visualmente una partida terminada.
- El error `Not Found` reportado por el usuario se debió a backend legacy aún en8000 sirviendo frontend nuevo. Se reinició la API; `/api/v2/catalog` respondió200 con4 personajes y2 arenas.

## Proveedores reales

Jev `jev-1.13.0`: 12 peticiones válidas, cuatro personajes × fases activo/choque/remate. Las descripciones de acciones incluyen alcance y coste. En un combate de20s frente a referencia ofensiva:21 respuestas,5 acciones aplicadas,195 de daño,2 caducadas; p50≈368ms, p95≈966ms. Las14 respuestas rechazadas cambiaron de contexto/acción legal mientras el modelo resolvía; no se reemplazaron. Este resultado demuestra conexión real; no demuestra que el modelo juegue bien ni que toda respuesta llegue a tiempo.

Laya multilingual: pesos reales, CPU, preflight8 estados,12 respuestas válidas para personajes/fases. El ritmo nativo de800ms no resulta viable en esta CPU: las consultas activas midieron aproximadamente2.6–5.3s. En diagnóstico explícito con5000ms/6000ms de antigüedad:5 respuestas,2 acciones aplicadas,95 de daño; p50≈4008ms. Ese resultado no se mezcla con las métricas nativas. No se verificó CUDA.

## Gráficos y recursos

Intel Core i5-9400F,6 CPUs lógicas; backend Python3.11. Chromium headless usó **ANGLE SwiftShader por software**. Antes del batching estático midió aproximadamente2–7FPS a1440px,107 draw calls; por tanto **no se ha validado el objetivo de60FPS con GPU**. La escena agrupa geometría estática por material y limita partículas/pixel ratio. Después de agrupar el escenario:57 draw calls y27–33 geometrías; auditoría sin errores JS,2.5–4.7FPS por software. Las medidas de Chromium por software no predicen el rendimiento del navegador con aceleración de hardware.

Cambios repetidos de personaje mantuvieron una sola escena/canvas y77–83 geometrías antes de agrupar el escenario; no hubo errores JavaScript en la auditoría visual. Los cuatro GLB pesan2.9MiB en total (aprox.0.74MB cada uno), sin texturas/CDN externos. Incluyen18 huesos y25 clips cada uno. Las capturas desktop/móvil y de remate están en `docs/screenshots/`. `eclipse-demo.webm` graba un combate local real de referencia en Chromium por software (calidad baja), incluida su detención.

La música y efectos originales usan Web Audio, paneo horizontal y variación de intensidad con la fase de combate. No se realizó una evaluación auditiva subjetiva del balance sonoro.

## Estabilidad sostenida

El primer tramo de referencia/referencia mantuvo unos60 ticks/s hasta1391s, con3105/3104 acciones aplicadas. Su proceso terminó conSIGTERM (exit143), sin excepción del motor registrada. No se declara una ejecución continua de30min. El segundo tramo completó480s activos (aprox.28800 ticks) sin error. Total verificado:1871s activos,31min11s, en dos tramos. El pico RSS del coordinador se registra en `evidence/soak.json`; incluye procesos separados de prueba, no una medición de fuga del navegador. No se declara una ejecución continua de30min.

Las credenciales reales permanecen en `.env` ignorado. `providers.local.json` también está excluido de Git y Docker. No se probaron despliegue Docker ni multijugador remoto; la app es local.

## Publicación

`main` y `combat-v2` publicados; `legacy` permanece en8f228fb y el tag `arena-legacy-v1`. Backend final reiniciado enlocalhost:8000 cuando ya no había encuentros activos. Salud y catálogo verificados porHTTP.
