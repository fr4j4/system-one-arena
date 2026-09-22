# Protocolo de combate · combat/1

El núcleo no conoce Jev, Laya ni HTTP. `observation.py` compila estado público a una única pregunta `choice`; cada perfil traduce la misma información a su proveedor. El catálogo de reglas está versionado, separado del contenido visual.

## Petición

```json
{
  "protocol_version": "1.0",
  "schema_id": "combat/1",
  "run_id": "match-id",
  "request_id": "unique-id",
  "episode_id": "match-id:epoch",
  "state_seq": 360,
  "budget_ms": 800,
  "max_state_age_ms": 1000,
  "state": {
    "scenario": "combat",
    "player_id": "p1",
    "phase": "active",
    "distance": 4,
    "self": {"character":"ember", "x":-2,"y":0,"hp":900,"energy":35,"guard":80},
    "opponent": {"character":"flux", "x":2,"y":0,"hp":850,"energy":15,"guard":100}
  },
  "questions": {
    "action": {
      "type": "choice",
      "instructions": "Choose the best legal action; consider reach and energy.",
      "criteria": {"forward":"approach enemy", "bolt":"projectile: reach 20m, cost 15"}
    }
  },
  "allowed_actions": ["forward", "bolt"]
}
```

Ejemplo abreviado: la petición real incluye reloj/rondas, orientación, movimiento actual y frame, stun/invulnerabilidad/combo, paredes, proyectiles, tabla compacta de técnicas y cuatro eventos recientes. Los tiempos son frames a 60 Hz, posiciones metros. No se envían geometría, píxeles, secretos, decisiones futuras del rival ni razonamiento interno. Durante choques sólo se incluye el historial de pulsos ya revelados.

Respuesta del proveedor: `{"answers":{"action":{"type":"choice","choice":"bolt"}}}`. Se normaliza a `answers.action.value`; distribución opcional sólo si el proveedor la entrega y pasa validación (todas las opciones, finita, suma válida). No se inventan probabilidades ni confianza para modelos genéricos.

## Ejecución y caducidad

- 3 consultas/s máximas por jugador; nunca más de una llamada física pendiente en cada slot. Los slots comparten un semáforo por recurso del proveedor; Laya CPU/GPU serializa por dispositivo.
- 800 ms de plazo en modo nativo; máximo 1000 ms de antigüedad. El modo experimental de ventanas comunes aplica al cerrar 800 ms y se reporta separado.
- Cambio de ronda, pulso, pausa/reanudación, reinicio o cinemática incrementa `epoch`. Se revalida contexto, plazo, legalidad y estado del encuentro antes de aplicar.
- Una respuesta tardía se registra y se descarta. Esperar a su finalización física evita saturar el proveedor con llamadas abandonadas. Detener congela inmediatamente la simulación y prohíbe nuevos envíos.
- Tres errores consecutivos o cinco segundos sin acción útil pausan con diagnóstico visible. Un proveedor nunca se reemplaza silenciosamente por la referencia.
- Avance/retroceso duran hasta400ms, guardia600ms, carga800ms; humano refresca mientras mantiene el control. No se consulta durante acciones comprometidas sin opciones legales.
- Rutas de combo: secuencias preautorizadas, continuaciones marcadas `route` y correlacionadas con la decisión. `engine` y `fallback` identifican exclusivamente reglas automáticas explícitas.

Laya usa tokenizer real para preflight y rechaza presupuestos insuficientes. No se trunca silenciosamente información táctica. Las latencias incluyen la inferencia del adaptador; el proceso de combate sigue a 60 Hz aunque el proveedor tarde.

## API / WebSocket

`GET /api/v2/catalog`, `/profiles`, `/health`. `POST /preview` crea estado local sin inferencia. `POST /matches` recibe `MatchConfig`; admite sólo un encuentro/serie activo en esta app local. `POST /matches/{id}/control`: pause/resume/stop/reset/step/skip. `GET /matches` y `/{id}` ofrecen estado/historial. `GET /matches/{id}/events?after=0&limit=5000` pagina eventos; `/export` entrega JSONL. `POST /series` recibe `{match,pairs}`; `GET /series`; `POST /series/{id}/stop`.

`WS /api/v2/matches/{id}/live?role=controller|spectator`: snapshot inicial, snapshots30Hz, decisiones, métricas, cambios de estado, eventos, finalización. Entrada humana `{kind:"input",player:0,action:"light",seq:1}` con secuencia monotónica y ack; `release:true` libera controles. Desconectar un controlador humano pausa. HTTP/WS rechazan otros orígenes; es una aplicación local, no un servicio público autenticado.

Cada replay conserva versiones de reglas/contenido, perfiles sin credenciales, comandos, eventos y snapshots persistidos a10Hz. La reproducción sigue timestamps de eventos incluso después de reiniciar un ejercicio. La UI permite inspeccionar la solicitud/respuesta de cada slot y exportar para análisis externo.
