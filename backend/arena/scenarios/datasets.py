"""Versioned synthetic challenge corpus. Variants are identified, not independent observations."""

import copy
import random
from collections import Counter, defaultdict

VERSION = "synthetic-v2"
# Context is part of the decision: 24 distinct intents × 10 distinct constraints per corpus.
TICKETS = [
    ("billing", "Me cobraron dos veces la misma compra; solicito la devolución."),
    ("billing", "La factura contiene un impuesto que no corresponde a mi país."),
    ("billing", "Cancelé la suscripción, pero sigue apareciendo un cargo mensual."),
    ("billing", "El pago fue aprobado por mi banco y figura pendiente en su sistema."),
    ("billing", "Necesito corregir la razón social de una factura ya emitida."),
    ("billing", "Solicito el comprobante de pago para conciliar la contabilidad."),
    ("technical", "La exportación de informes termina con un error 500."),
    ("technical", "Al iniciar sesión aparece una pantalla en blanco."),
    ("technical", "Las notificaciones llegan repetidas y fuera de orden."),
    ("technical", "Los archivos adjuntos no se descargan desde la aplicación."),
    ("technical", "La integración dejó de sincronizar los cambios del inventario."),
    ("technical", "La búsqueda devuelve documentos que ya fueron eliminados."),
    ("sales", "Quiero conocer el precio para incorporar veinte licencias."),
    ("sales", "Necesito una cotización anual con soporte dedicado."),
    ("sales", "Estamos comparando planes: ¿cuál incluye auditoría y SSO?"),
    ("sales", "Solicito una demostración antes de contratar el servicio."),
    ("sales", "¿Existe un descuento para organizaciones educativas?"),
    ("sales", "Queremos negociar las condiciones de renovación del contrato."),
    ("other", "Quiero solicitar una copia de mis datos personales."),
    ("other", "Necesito actualizar el nombre público de nuestra organización."),
    ("other", "¿Dónde puedo consultar la política de conservación de datos?"),
    ("other", "Quisiera proponer una colaboración para un evento comunitario."),
    ("other", "Solicito información sobre las opciones de accesibilidad."),
    ("other", "Necesito saber cómo presentar una sugerencia de producto."),
]
TICKET_CONTEXT = [
    ("Es una consulta para el próximo mes; no hay bloqueo ni plazo cercano.", 0, 0, "claro"),
    ("Afecta solo a mi cuenta. Puedo seguir trabajando, pero agradecería atención pronto.", 1, 0, "claro"),
    ("El plazo contractual vence hoy y no podemos terminar el trámite sin resolverlo.", 2, 0, "difícil"),
    (
        "El asunto nos interesa para planificar el próximo trimestre; no requiere respuesta urgente.",
        0,
        0,
        "claro",
    ),
    (
        "Lo necesitamos para una revisión durante esta semana, aunque existe una alternativa temporal.",
        1,
        0,
        "difícil",
    ),
    (
        "Además hay una caída del servicio: ninguna de las 80 personas del equipo puede trabajar. Prioricen esa caída y deriven a soporte técnico.",
        2,
        1,
        "difícil",
    ),
    (
        "El mensaje anterior decía URGENTE por error. Ya resolvimos el bloqueo; esta consulta restante puede esperar.",
        0,
        0,
        "difícil",
    ),
    (
        "No es una caída general. Solo yo estoy afectado y puedo usar la versión web mientras lo revisan.",
        1,
        0,
        "difícil",
    ),
    (
        "Es para ahora: tenemos un vencimiento en una hora, aunque las demás cuentas funcionan.",
        2,
        0,
        "difícil",
    ),
    ("No tengo más detalles sobre el impacto ni sobre el plazo; ¿pueden orientarme?", [0, 1], 0, "ambiguo"),
]
EMAIL_TOPICS = [
    "contrato de mantenimiento",
    "presupuesto del trimestre",
    "informe de ventas",
    "agenda del taller",
    "acuerdo de confidencialidad",
    "plan de migración",
    "inventario de equipos",
    "acta de reunión",
    "calendario de entregas",
    "documentación de seguridad",
    "encuesta de satisfacción",
    "propuesta de diseño",
    "resultado de auditoría",
    "manual de incorporación",
    "resumen de incidencias",
    "programa de formación",
    "plan de vacaciones",
    "balance de gastos",
    "revisión de accesibilidad",
    "certificado de servicio",
    "lista de asistentes",
    "guía de integración",
    "informe de sostenibilidad",
    "resumen del proyecto",
]
EMAIL_CONTEXT = [
    (
        "Necesito que revises el {topic} y me confirmes si lo apruebas antes del viernes.",
        "request",
        1,
        "claro",
    ),
    (
        "Adjunto el {topic} únicamente para tu información. No hace falta responder.",
        "information",
        0,
        "claro",
    ),
    (
        "Oferta exclusiva: adquiere nuestro paquete de {topic} con 30% de descuento. Compra en la tienda.",
        "promotion",
        0,
        "claro",
    ),
    (
        "En el hilo anterior pedí aprobar el {topic}. Retiro esa solicitud: ya fue aprobado y este correo solo deja constancia.",
        "information",
        0,
        "difícil",
    ),
    (
        "Aunque el asunto dice 'informativo', falta tu autorización del {topic}. Por favor responde con tu decisión.",
        "request",
        1,
        "difícil",
    ),
    (
        "Recibí una promoción sobre el {topic}, pero te escribo para pedir que revises el documento interno adjunto y me respondas.",
        "request",
        1,
        "difícil",
    ),
    (
        "Lanzamos un nuevo servicio de {topic}. Si te interesa, visita nuestro catálogo; este es un anuncio comercial.",
        "promotion",
        0,
        "claro",
    ),
    (
        "Se actualizó el {topic}. El aviso es automático y esta dirección no recibe respuestas.",
        "information",
        0,
        "claro",
    ),
    (
        "¿Podrías enviarme el {topic}? No necesito que acuses recibo, pero sí que contestes adjuntando el documento.",
        "request",
        1,
        "difícil",
    ),
    (
        "Te comparto el {topic}; quizá puedas mirarlo cuando tengas tiempo. No sé si hace falta tu confirmación.",
        ["information", "request"],
        [0, 1],
        "ambiguo",
    ),
]
SPAM_TOPICS = [
    "cuenta bancaria",
    "servicio de correo",
    "suscripción de música",
    "tienda de libros",
    "plataforma de cursos",
    "servicio de almacenamiento",
    "cuenta de videojuegos",
    "programa de viajes",
    "servicio de telefonía",
    "plataforma de facturación",
    "club deportivo",
    "tienda de ropa",
    "servicio de mensajería",
    "plataforma de inversiones",
    "biblioteca digital",
    "portal de seguros",
    "servicio de streaming",
    "aplicación de transporte",
    "proveedor de internet",
    "portal de empleo",
    "tienda de electrónica",
    "servicio de reservas",
    "programa de recompensas",
    "cuenta corporativa",
]
SPAM_CONTEXT = [
    (
        "Aviso sobre tu {topic}: tu estado mensual está disponible. Entra desde la aplicación que ya tienes instalada. No pedimos datos por correo.",
        0,
        0,
        "claro",
    ),
    (
        "Tu {topic} será bloqueada hoy. Contesta este correo con tu contraseña y código de verificación para evitarlo.",
        [0, 1],
        1,
        "claro",
    ),
    (
        "Publicidad no solicitada de {topic}: descuento especial del 40%, compra hoy. No solicita claves ni pagos fuera de la tienda.",
        1,
        0,
        "claro",
    ),
    (
        "Ganaste un premio de {topic} sin participar. Para cobrarlo envía tus credenciales y paga una comisión a una cuenta personal.",
        1,
        1,
        "claro",
    ),
    (
        "Boletín de {topic} que solicitaste recibir: nuevas ofertas del mes. Puedes darte de baja. No se solicita información sensible.",
        0,
        0,
        "difícil",
    ),
    (
        "Capacitación interna sobre {topic}: el ejemplo 'envía tu contraseña' ilustra un fraude. Nunca respondas con credenciales; este mensaje no las solicita.",
        0,
        0,
        "difícil",
    ),
    (
        "Soy soporte de {topic}. No compartas tu contraseña: solo necesito que me reenvíes el código de un solo uso para 'verificar' tu identidad.",
        [0, 1],
        1,
        "difícil",
    ),
    (
        "Sobre {topic}, soy tu gerente. Cambió nuestra cuenta de pago: transfiere urgentemente a esta cuenta personal sin llamar a contabilidad; mantenlo en secreto.",
        [0, 1],
        1,
        "difícil",
    ),
    (
        "Respuesta al caso que abriste sobre {topic}: recibimos tu consulta. No realices pagos ni envíes claves; responderemos en el portal oficial.",
        0,
        0,
        "claro",
    ),
    (
        "Recomendación de {topic}: aprovecha la promoción de esta semana. No consta si el destinatario aceptó recibir publicidad y no hay solicitud de credenciales.",
        [0, 1],
        0,
        "ambiguo",
    ),
]


def corpus(name):
    rows = []
    if name not in ("tickets", "email", "spam"):
        return rows
    topics = TICKETS if name == "tickets" else EMAIL_TOPICS if name == "email" else SPAM_TOPICS
    contexts = TICKET_CONTEXT if name == "tickets" else EMAIL_CONTEXT if name == "email" else SPAM_CONTEXT
    for i, topic in enumerate(topics):
        for j, context in enumerate(contexts):
            if name == "tickets":
                suffix, priority, escalate, difficulty = context
                department, text = topic
                if escalate:
                    department = "technical"
                state = {"text": f"{text}\n{suffix}"}
                expected = {"department": department, "priority": priority, "escalate": escalate}
                rationale = f"Destino {department}; prioridad según el impacto/plazo explícito; escalamiento solo ante caída multiusuario."
                group = department
            elif name == "email":
                template, intent, reply, difficulty = context
                state = {"text": template.format(topic=topic)}
                expected = {"intent": intent, "reply": reply}
                rationale = "La intención vigente prevalece sobre el asunto y las solicitudes retiradas; responder incluye enviar el documento pedido."
                group = intent if isinstance(intent, str) else "ambiguo"
            else:
                template, spam, phishing, difficulty = context
                state = {"text": template.format(topic=topic)}
                expected = {"spam": spam, "phishing": phishing}
                rationale = "Spam exige publicidad no solicitada; phishing incluye robo de códigos o pagos engañosos. Una cita educativa no es una solicitud."
                group = (
                    "phishing"
                    if phishing
                    else "spam"
                    if spam == 1
                    else "legítimo"
                    if spam == 0
                    else "ambiguo"
                )
            rows.append(
                {
                    "id": f"{name}-v2-{i:02}-{j:02}",
                    "state": state,
                    "expected": expected,
                    "metadata": {
                        "source": "Sintético · composición revisable",
                        "version": VERSION,
                        "family": f"{name}-intent-{i:02}",
                        "variant": j,
                        "difficulty": difficulty,
                        "language": "es",
                        "group": group,
                        "rationale": rationale,
                    },
                }
            )
    return rows


def sample(items, size=None, strategy="random", seed=42, difficulty="all"):
    pool = [
        copy.deepcopy(x)
        for x in items
        if difficulty == "all" or x.get("metadata", {}).get("difficulty") == difficulty
    ]
    if not pool:
        raise ValueError("No hay casos para el filtro seleccionado")
    rng = random.Random(seed)
    rng.shuffle(pool)
    count = min(size or len(pool), len(pool))
    if strategy == "balanced":
        groups = defaultdict(list)
        for row in pool:
            label = row.get("metadata", {}).get("group")
            if label is None:
                label = str(next(iter(row.get("expected", {}).values()), "sin etiqueta"))
            groups[str(label)].append(row)
        pool = []
        while groups:
            for label in list(groups):
                pool.append(groups[label].pop())
                if not groups[label]:
                    del groups[label]
    selected = pool[:count]
    return selected, {
        "available": len(pool),
        "selected": len(selected),
        "requested": size,
        "strategy": strategy,
        "seed": seed,
        "difficulty": difficulty,
        "ids": [r["id"] for r in selected],
        "groups": dict(Counter(r.get("metadata", {}).get("group", "sin grupo") for r in selected)),
        "versions": sorted({r.get("metadata", {}).get("version", "importado") for r in selected}),
    }
