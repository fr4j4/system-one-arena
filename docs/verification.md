# Verificación · Eclipse Arena

Ejecutado localmente el 2026-09-22. Evidencia de proveedores en `docs/combat/evidence/`. Estas cifras corresponden a este equipo y a las peticiones de prueba, no a garantías del proveedor.

## Motor, API y navegador

- 83 pruebas de Python aprobadas (2026-09-22, tras el cambio de sincronización): reglas, recursos, cancelaciones, cuerpos, combos, proyectiles, guardia/parry, choques sellados, remates, presets, replay determinista, fases, concurrencia, plazos, pausa/stop, perfiles, series, protocolo, persistencia y GLB originales.
- Ruff check y format sin errores; frontend TypeScript + Vite compilado y Prettier verificado.
- Seis pruebas de navegador aprobadas: selección independiente de slots; decisiones y pausa/stop sin nuevas llamadas; teclado y pérdida de foco; reasignación; choque y remate; series emparejadas y replay; móvil sin overflow. Control de mando probado con Gamepad API simulada, no con hardware físico.
- El bug de fin de remate se corrigió notificando estado final antes de esperar cierre de procesos/llamadas, y evitando que una respuesta HTTP antigua reabra visualmente una partida terminada.
- El error `Not Found` reportado por el usuario se debió a backend legacy aún en8000 sirviendo frontend nuevo. Se reinició la API; `/api/v2/catalog` respondió200 con4 personajes y2 arenas.

## Proveedores reales

Jev `jev-1.13.0`: 12 peticiones válidas, cuatro personajes × fases activo/choque/remate. Las descripciones de acciones incluyen alcance y coste. En un combate de20s frente a referencia ofensiva:21 respuestas,5 acciones aplicadas,195 de daño,2 caducadas; p50≈368ms, p95≈966ms. Las14 respuestas rechazadas cambiaron de contexto/acción legal mientras el modelo resolvía; no se reemplazaron. Este resultado demuestra conexión real; no demuestra que el modelo juegue bien ni que toda respuesta llegue a tiempo.

Benchmark `scripts/bench_jev.py`, 3 combates × 30s, ritmo nativo, Jev contra referencia (ember/flux rotando lados). Antes (`evidence/bench-jev-before.json`): 91 respuestas, 65 aplicadas (tasa 0.714), 1 caducada, 25 rechazadas (23 `illegal_action`, 2 `context_changed`); p50≈278ms, p95≈350ms; daño 1245 hecho / 3138 recibido; 0 victorias, 3 derrotas (ver nota de resultados abajo). El diagnóstico por evento mostró 12 peticiones construidas ≤2 ticks después de la acción anterior aplicada, sobre un snapshot que aún no la reflejaba; 9 rechazos ocurrieron con Jev dentro de su propio movimiento y 13 aturdido por un golpe recibido mientras el modelo resolvía.

Cambio: el slot espera el ack de su acción y un snapshot posterior antes de consultar de nuevo (ver `protocol.md`). Después (`evidence/bench-jev-after.json`): 77 respuestas, 59 aplicadas (tasa 0.766), 1 caducada, 17 rechazadas (16 `illegal_action`, 1 `context_changed`); p50≈289ms, p95≈365ms; daño 955 / 3971; 0 victorias, 3 derrotas. Nota de resultados: el campo `winner` de ambos JSON se calculó con un `winner()` que ignoraba las rondas ganadas y comparaba solo la vida de la ronda en curso al llegar al límite de tiempo (corregido en `bench_jev.py`). En los tres combates de cada archivo Jev recibió más de 1000 de daño (vida máxima 1000, rondas de 90s en un combate de 30s), es decir, perdió al menos una ronda por KO, y el rival recibió menos de 1000 y no perdió ninguna; los "empates" y la "victoria" registrados eran derrotas por rondas. Rechazos con Jev en su propio movimiento: 0 (antes 9); peticiones sobre snapshot obsoleto: 0 (antes 12). La tasa sube en los tres combates (0.727/0.667/0.750 → 0.741/0.739/0.815), pero el total absoluto de acciones aplicadas bajó (65 → 59): las llamadas obsoletas a veces acertaban por solaparse con la recuperación. Con 3 combates, daño y resultado están dentro del ruido; no se afirma mejora de juego. De los 17 rechazos restantes, 12 ocurren con Jev aturdido por un golpe recibido durante la latencia, donde la acción es realmente ilegal; los otros 5 no se diagnosticaron (posiblemente pausa de impacto, sin verificar). Ninguno se reemplaza ni se aplica.

Tras corregir la referencia (espejo sin daño: umbral de combo y moneda determinista dash/rayo), el rival ataca de verdad y las cifras anteriores dejan de ser comparables. Final (`evidence/bench-jev-final.json`, 3 × 30s): 76 respuestas, 42 aplicadas (tasa 0.553), 3 caducadas, 31 rechazadas (28 `illegal_action`, 3 `context_changed`); p50≈305ms, p95≈727ms; daño 430 hecho / 5421 recibido; 0 victorias, 3 derrotas. La mayor presión aturde más a Jev durante la latencia, lo que eleva `illegal_action`. Jev pierde con claridad contra la referencia.

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
