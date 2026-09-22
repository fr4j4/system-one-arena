# Reglas de combate · combat-1.0.0

El servidor es la autoridad: 60 frames/s, posiciones en milímetros y recursos en centipuntos. El cliente dibuja metros. Z siempre es cero. Un golpe depende del frame activo, alcance horizontal, altura y defensa; nunca de una colisión visual.

## Victoria y recursos

1000 PV, 25 EN iniciales, máximo 100 EN, 100 de guardia. Mejor de 1/3/5, por KO o más PV al terminar el tiempo. Empates no conceden ronda; límite total de rondas = formato + 2. Golpes simultáneos se resuelven juntos. Las pausas, cinemáticas y choques suspenden el reloj de ronda.

Energía: +2/s al esperar/caminar; cargar tarda 15 frames en comenzar y recupera 12/s. Golpe básico acertado +3 (fuerte +5), recibir impacto +2, parry +8. Los poderes no regeneran energía al golpear. Coste al comenzar, sin devolución. Guardia regenera 20/s tras 60 frames sin bloqueo/impacto. Al romperse, aturdimiento 45 frames y recuperación a 50.

## Movimiento y defensa

Avance 4.5 m/s, retroceso 3.6 m/s. Salto vertical o dirigido. Dash 1.8 m/12 frames, cooldown 30, sin invulnerabilidad. Evasión: 20 EN, 8 frames invulnerables, cooldown 90. Separación de cuerpos en el mismo nivel; salto permite cruce. Límites de centro ±9.5 m.

Guardia alta pierde ante bajo; baja pierde ante overhead. Agarre vence ambas. Primeros 6 frames de guardia nueva permiten parry, rearme 30 frames; rayos y definitivas no son parryables. Bloqueo físico no causa chip; poderes causan 10%, sin matar. Escape cuesta 50 EN, una vez por combo; no sirve contra agarres, choque ni cinemáticas.

## Ataques

| Acción | EN | Daño | Inicio / activo / recuperación | Alcance |
|---|---:|---:|---|---|
| Ligero | 0 | 40 | 6 / 3 / 12 | 1.2 m |
| Fuerte | 0 | 85 | 14 / 4 / 24 | 1.8 m |
| Bajo | 0 | 55 | 10 / 3 / 20 | 1.5 m |
| Overhead | 0 | 75 | 20 / 4 / 24 | 1.5 m |
| Lanzador | 10 | 65 | 16 / 3 / 26 | 1.4 m |
| Agarre | 0 | 90 | 12 / 2 / 28 | 0.9 m |
| Proyectil | 15 | 65 | 18 / 1 / 20 | Viaja |
| Rayo | 35 | 140 | 36 / 24 / 36 | Viaja |
| Definitiva | 100 | 340 | 36 / 6 / 48 | 2.5 m |
| Aéreo fuerte | 0 | 70 | 8 / 4 / 20 | 1.6 m |

Técnicas propias, 25 EN: Ember 3×35, alcance2 m; Flux 90 y dash; Terra110 con armadura para un golpe (recibe daño, ignora interrupción; excluye agarre/definitiva); Nyx100 como contra a golpe medio durante su ventana activa.

Rutas: ligero–ligero–fuerte; ligero–lanzador–aéreo; ligero–fuerte–técnica; dash–ligero–proyectil. Cancelación sólo tras impacto; fallo o interrupción termina ruta; bloqueo detiene la secuencia y autoriza guardia breve. Escalado 100/85/70/55/40%; seis impactos o tres aéreos fuerzan derribo y recuperación protegida. Buffer humano de seis frames. Las rutas son acciones explícitas del controlador, no decisiones añadidas por otro agente.

## Choques y remates

Dos rayos enfrentados que colisionan abren tres pulsos simultáneos de 800 ms. Cada jugador confirma una opción por pulso:

| Elección | EN | Fuerza |
|---|---:|---:|
| Sostener | 0 | 1 |
| Impulsar | 10 | 2 |
| Sobrecargar | 20 | 4; 2 si se repite consecutivamente |
| Ceder | 0 | Sale recibiendo 40; ambos ceden = 0 |

Las elecciones permanecen selladas hasta el cierre. Sin respuesta: sostener, etiquetado `fallback`. Mayor fuerza gana, daño `min(200, 140 + 8 × diferencia)`; empate disipa los rayos.

Después del KO que gana el encuentro, hay tres segundos para rematar o perdonar. Remate de cinco segundos, omisible, sin cambiar resultado ni gastar energía. Definitiva confirmada: pausa cinematográfica de 1.5 s. Los ejercicios de remate/choque preparan esas fases directamente y se identifican como entrenamiento.
