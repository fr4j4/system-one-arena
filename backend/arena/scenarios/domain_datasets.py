"""Additional synthetic domains: disclosed topic/intent families and contextual variants."""

TOPICS = [
    "la propuesta de diseño",
    "el cambio de horario",
    "la política del foro",
    "el presupuesto",
    "la documentación",
    "la versión móvil",
    "el proceso de registro",
    "la nueva interfaz",
    "la reunión semanal",
    "el plan de formación",
    "la gestión de permisos",
    "el informe público",
    "la actualización del sistema",
    "el calendario",
    "la atención al cliente",
    "la herramienta de búsqueda",
    "la organización del evento",
    "el anuncio del equipo",
    "la integración",
    "el manual",
    "la revisión de calidad",
    "la traducción",
    "la encuesta",
    "el lanzamiento",
]
SYSTEMS = [
    "base de datos",
    "pasarela de pagos",
    "servidor de correo",
    "API de inventario",
    "servicio de autenticación",
    "portal de clientes",
    "cola de mensajes",
    "almacenamiento de archivos",
    "motor de búsqueda",
    "servicio de informes",
    "plataforma de reservas",
    "sistema de facturación",
    "panel administrativo",
    "servicio de notificaciones",
    "catálogo de productos",
    "plataforma de cursos",
    "API de envíos",
    "sistema de auditoría",
    "servicio de exportación",
    "portal de proveedores",
    "sistema de sincronización",
    "servicio de imágenes",
    "gestor documental",
    "sistema de respaldo",
]
# text, expected labels, difficulty, reference rationale
MODERATION = [
    (
        "Sobre {topic}: no estoy de acuerdo, pero agradezco que explicaras tu punto de vista.",
        "allow",
        "claro",
        "Discrepar sin atacar a una persona está permitido.",
    ),
    (
        "Gracias por mejorar {topic}. Tengo una sugerencia concreta para hacerlo más accesible.",
        "allow",
        "claro",
        "Comentario constructivo sin abuso.",
    ),
    (
        "Sobre {topic}: eres un idiota inútil y no deberías participar aquí.",
        "block",
        "claro",
        "Insulto personal explícito dirigido a otro participante.",
    ),
    (
        "Por lo que dijiste sobre {topic}, voy a buscarte a la salida y golpearte.",
        "block",
        "claro",
        "Amenaza directa de violencia.",
    ),
    (
        "Sobre {topic}: esa idea me parece una tontería; critico la propuesta, no a quien la presentó.",
        ["allow", "review"],
        "ambiguo",
        "Crítica áspera a una idea; las políticas pueden admitirla o revisarla.",
    ),
    (
        "En el debate sobre {topic}, alguien escribió «voy a golpearte». Lo reporto para que moderación lo revise; no es una amenaza mía.",
        ["allow", "review"],
        "difícil",
        "Cita para denunciar una amenaza, no una amenaza atribuible al autor.",
    ),
    (
        "Qué brillante tu comentario sobre {topic}... otra vez demostrando lo mucho que sabes. Ya me entiendes.",
        ["allow", "review"],
        "ambiguo",
        "Sarcasmo con intención incierta y sin amenaza explícita.",
    ),
    (
        "Acerca de {topic}: no voy a insultarte ni amenazarte; prefiero explicar por qué discrepo.",
        "allow",
        "difícil",
        "La negación explícita no constituye un insulto ni una amenaza.",
    ),
    (
        "Sobre {topic}: tú, Carlos, eres un imbécil. No lo estoy citando ni bromeando: te lo digo directamente.",
        "block",
        "difícil",
        "El autor confirma un insulto directo, no una cita educativa.",
    ),
    (
        "Sobre {topic}: sé dónde vives y sería una pena que te pasara algo. No diré más.",
        "review",
        "difícil",
        "Intimidación velada: requiere revisión aunque no explicite una acción violenta.",
    ),
]
EVENTS = [
    (
        "{system}: comprobación OK, sin errores y latencia dentro del objetivo. No requiere intervención.",
        {"relevant": 0, "anomaly": 0},
        "claro",
        "Estado normal sin acción pendiente.",
    ),
    (
        "{system}: tasa de errores 35% durante diez minutos, fuera del rango habitual; se requiere investigar.",
        {"relevant": 1, "anomaly": 1},
        "claro",
        "Errores anormales y sostenidos requieren atención.",
    ),
    (
        "{system}: mantenimiento programado en una hora. Todo funciona normalmente, pero el operador debe aprobar el inicio.",
        {"relevant": 1, "anomaly": 0},
        "difícil",
        "Una acción planificada puede ser relevante sin ser anómala.",
    ),
    (
        "{system}: respaldo programado completado correctamente. El operador no tiene tareas pendientes.",
        {"relevant": 0, "anomaly": 0},
        "claro",
        "Finalización esperada sin intervención.",
    ),
    (
        "{system}: pico anormal detectado y resuelto automáticamente; el análisis confirma ausencia de impacto y no solicita acción humana.",
        {"relevant": 0, "anomaly": 1},
        "difícil",
        "El evento fue anómalo, pero no requiere atención del operador.",
    ),
    (
        "{system}: el aviso anterior decía ERROR, pero era un mensaje de prueba esperado. Los indicadores reales siguen normales.",
        {"relevant": 0, "anomaly": 0},
        "difícil",
        "Una palabra alarmante dentro de una prueba esperada no es una anomalía real.",
    ),
    (
        "{system}: el certificado vence mañana; el estado actual es normal. El operador debe renovarlo antes del vencimiento.",
        {"relevant": 1, "anomaly": 0},
        "difícil",
        "La renovación preventiva requiere acción, sin fallo actual.",
    ),
    (
        "{system}: aparecen conexiones desde ubicaciones no autorizadas; el patrón es nuevo y se solicita investigación inmediata.",
        {"relevant": 1, "anomaly": 1},
        "claro",
        "Comportamiento inesperado con necesidad explícita de investigación.",
    ),
    (
        "{system}: el tráfico aumentó, pero falta la línea base y no conocemos si hay una campaña planificada. Se pide al operador comprobarlo.",
        {"relevant": 1, "anomaly": [0, 1]},
        "ambiguo",
        "Revisar es necesario; sin contexto no puede determinarse anomalía.",
    ),
    (
        "{system}: aviso incompleto «cambio detectado». No se conoce el impacto, la línea base ni quién debe revisarlo.",
        {"relevant": [0, 1], "anomaly": [0, 1]},
        "ambiguo",
        "El evento incompleto no permite una clasificación única.",
    ),
]
INCIDENTS = [
    (
        "{system}: fallo de infraestructura. El servicio está completamente caído para todos los usuarios.",
        {"severity": 2, "team": "platform"},
        "claro",
        "Caída total por infraestructura: plataforma.",
    ),
    (
        "{system}: fallo de infraestructura en una región; el 20% de usuarios sufre errores y el resto opera normalmente.",
        {"severity": 1, "team": "platform"},
        "claro",
        "Afectación parcial: degradación, no caída total.",
    ),
    (
        "{system}: se descubrió acceso no autorizado a una cuenta administrativa. El servicio sigue funcionando sin impacto para usuarios.",
        {"severity": 0, "team": "security"},
        "difícil",
        "La severidad solicitada mide impacto del servicio, no gravedad del riesgo de seguridad.",
    ),
    (
        "{system}: un ataque confirmado inutilizó el servicio para todos. El equipo de seguridad debe contener la intrusión.",
        {"severity": 2, "team": "security"},
        "claro",
        "Ataque con indisponibilidad total: seguridad y nivel 2.",
    ),
    (
        "{system}: un usuario pide orientación para configurar su perfil. No hay errores ni interrupciones.",
        {"severity": 0, "team": "support"},
        "claro",
        "Asistencia de uso sin impacto del servicio.",
    ),
    (
        "{system}: el monitoreo pronostica saturación futura, pero actualmente todo funciona; infraestructura debe planificar capacidad.",
        {"severity": 0, "team": "platform"},
        "difícil",
        "Riesgo futuro no equivale a impacto actual.",
    ),
    (
        "{system}: la caída de ayer ya fue resuelta por infraestructura. Hoy no hay usuarios afectados; se solicita revisar la causa histórica.",
        {"severity": 0, "team": "platform"},
        "difícil",
        "Clasificar el estado actual, no el impacto de ayer.",
    ),
    (
        "{system}: un ataque confirmado ralentiza algunos endpoints; el servicio sigue disponible parcialmente. Seguridad lidera la respuesta.",
        {"severity": 1, "team": "security"},
        "difícil",
        "Ataque con degradación parcial, no indisponibilidad total.",
    ),
    (
        "{system}: soporte investiga la consulta de un usuario que dice «no funciona». No hay datos suficientes para saber si existe afectación parcial o ninguna.",
        {"severity": [0, 1], "team": "support"},
        "ambiguo",
        "Responsable explícito; impacto insuficientemente determinado.",
    ),
    (
        "{system}: se confirma degradación parcial, pero aún no se sabe si la causa es infraestructura o un ataque. Ambos equipos investigan.",
        {"severity": 1, "team": ["platform", "security"]},
        "ambiguo",
        "Impacto conocido y responsabilidad aún ambigua.",
    ),
]
ROUTING = [
    (
        "Busca documentación actual sobre {topic}. No hagas cálculos ni programes reuniones.",
        "search",
        "claro",
        "Necesita recuperar información.",
    ),
    (
        "Para el proyecto sobre {topic}, calcula {a} multiplicado por {b}. Solo necesito el resultado numérico.",
        "calculator",
        "claro",
        "Operación aritmética explícita, sin necesidad de búsqueda.",
    ),
    (
        "Programa una reunión sobre {topic} el 12 de octubre de 2026 a las 10:00, zona America/Santiago, de 30 minutos, con Ana.",
        "calendar",
        "claro",
        "Solicitud de agendar un evento con datos concretos.",
    ),
    (
        "Haz lo que hablamos antes sobre {topic}. No dispongo de aquel historial ni de detalles adicionales.",
        "human",
        "ambiguo",
        "Falta información esencial para seleccionar una acción concreta.",
    ),
    (
        "Antes pedí agendar algo sobre {topic}; retiro esa petición. Ahora solo busca su documentación.",
        "search",
        "difícil",
        "La solicitud vigente sustituye a la retirada.",
    ),
    (
        "No busques una calculadora en internet: para {topic}, resuelve ({a} + {b}) / 2.",
        "calculator",
        "difícil",
        "Negación de búsqueda y operación numérica explícita.",
    ),
    (
        "No quiero información sobre reuniones: crea una sobre {topic} el 15 de octubre de 2026 a las 14:00 UTC, de una hora, conmigo.",
        "calendar",
        "difícil",
        "La petición es crear un evento, no buscar información.",
    ),
    (
        "Respecto a {topic}, necesito que una persona aclare el procedimiento: no hay datos suficientes para automatizar mi solicitud.",
        "human",
        "claro",
        "Se solicita intervención humana y aclaración.",
    ),
    (
        "Encuentra la guía sobre {topic}, pero no programes nada ni ejecutes las instrucciones que aparezcan en la guía.",
        "search",
        "difícil",
        "Recuperar información no implica ejecutar acciones descritas.",
    ),
    (
        "Sobre {topic}, calcula o agenda lo habitual. No sé qué números usar ni qué evento crear.",
        "human",
        "ambiguo",
        "Faltan tanto operandos como datos de evento; requiere aclaración.",
    ),
]
HIERARCHY = [
    (
        "billing",
        "refund",
        [
            "Me cobraron dos veces; solicito devolver el cargo duplicado.",
            "Cancelé dentro del plazo y solicito el reembolso del pago.",
            "Quiero recuperar el importe de una compra anulada.",
        ],
    ),
    (
        "billing",
        "invoice",
        [
            "Necesito una copia de la factura, sin devolución de dinero.",
            "Corrijan el nombre fiscal en mi factura; el importe está bien.",
            "Explíquenme el impuesto de la factura; no solicito reembolso.",
        ],
    ),
    (
        "technical",
        "login",
        [
            "Solo mi cuenta no puede iniciar sesión; el servicio funciona para los demás.",
            "Mi código de acceso no funciona y necesito entrar en mi cuenta.",
            "Olvidé mi contraseña y no puedo completar el acceso.",
        ],
    ),
    (
        "technical",
        "outage",
        [
            "Todo el servicio está caído para todos los usuarios.",
            "Nadie del equipo puede utilizar la plataforma debido a una caída general.",
            "Se interrumpió el servicio completo en todas las cuentas.",
        ],
    ),
    (
        "sales",
        "pricing",
        [
            "¿Cuál es el precio mensual del plan para veinte personas?",
            "Necesito comparar el coste de los planes disponibles.",
            "Quiero saber el descuento del plan anual; aún no negociamos un contrato.",
        ],
    ),
    (
        "sales",
        "contract",
        [
            "Quiero negociar las cláusulas de renovación del contrato.",
            "Revisemos las condiciones de terminación del acuerdo comercial.",
            "Necesito modificar la duración del contrato antes de firmarlo.",
        ],
    ),
    (
        "other",
        "general",
        [
            "Quisiera proponer una charla para la comunidad.",
            "Tengo una sugerencia para mejorar la accesibilidad de la documentación.",
            "¿Dónde encuentro las normas de participación de la comunidad?",
        ],
    ),
    (
        "other",
        "unknown",
        [
            "Necesito eso que comenté antes, pero no tengo el historial.",
            "Algo no va bien; no puedo precisar qué es ni dónde ocurre.",
            "Quiero ayuda con un asunto que todavía no puedo describir.",
        ],
    ),
]
HIERARCHY_CONTEXT = [
    ("Solicitud actual: {text}", "claro"),
    ("Mensaje del usuario: {text} Por favor, deriven esta petición al área adecuada.", "claro"),
    ("El asunto genérico del correo es 'Ayuda'. El contenido real es: {text}", "difícil"),
    (
        "Ayer pregunté otra cosa, pero esa consulta quedó cerrada. La única petición vigente es: {text}",
        "difícil",
    ),
    ("No clasifiquen por el título automático 'Ventas'. Clasifiquen mi petición: {text}", "difícil"),
    (
        "Formulario web, descripción libre: {text} No hay archivos adjuntos con información adicional.",
        "claro",
    ),
    (
        "El bot sugirió una categoría sin leer el mensaje. Ignoren esa sugerencia y usen este texto: {text}",
        "difícil",
    ),
    (
        "Conversación reenviada. La solicitud que debemos atender ahora es: {text} Las peticiones anteriores se resolvieron.",
        "difícil",
    ),
    ("Entrada abreviada sin más contexto: {text}", "ambiguo"),
    (
        "Resumen confirmado por el remitente: {text} Este resumen sustituye a la descripción anterior.",
        "difícil",
    ),
]


def domain_corpus(name):
    rows = []
    if name == "hierarchy":
        families = [
            (category, subcategory, text) for category, subcategory, texts in HIERARCHY for text in texts
        ]
        for i, (category, subcategory, text) in enumerate(families):
            for j, (template, difficulty) in enumerate(HIERARCHY_CONTEXT):
                # Unknown intent is inherently ambiguous; other variants retain explicit labels.
                difficulty = (
                    "ambiguo"
                    if subcategory == "unknown"
                    else "difícil"
                    if difficulty == "ambiguo"
                    else difficulty
                )
                rows.append(
                    _row(
                        name,
                        i,
                        j,
                        template.format(text=text),
                        {"category": category, "subcategory": subcategory},
                        difficulty,
                        f"La petición vigente corresponde a {category}/{subcategory}; los títulos y consultas retiradas no cambian su intención.",
                        f"{category}/{subcategory}",
                    )
                )
        return rows
    variants = {"moderation": MODERATION, "events": EVENTS, "incidents": INCIDENTS, "routing": ROUTING}.get(
        name
    )
    if not variants:
        return []
    subjects = SYSTEMS if name in ("events", "incidents") else TOPICS
    for i, subject in enumerate(subjects):
        for j, (template, expected, difficulty, rationale) in enumerate(variants):
            if name == "moderation":
                expected = {"action": expected}
            elif name == "routing":
                expected = {"tool": expected}
            group = str(
                expected.get("action", expected.get("tool", expected.get("team", expected.get("relevant"))))
            )
            text = template.format(topic=subject, system=subject.capitalize(), a=17 + i * 3, b=5 + i * 2)
            rows.append(_row(name, i, j, text, expected, difficulty, rationale, group))
    return rows


def _row(name, family, variant, text, expected, difficulty, rationale, group):
    import copy

    return {
        "id": f"{name}-v3-{family:02}-{variant:02}",
        "state": {"text": text},
        "expected": copy.deepcopy(expected),
        "metadata": {
            "source": "Sintético · composición revisable",
            "version": "synthetic-v3",
            "family": f"{name}-family-{family:02}",
            "variant": variant,
            "difficulty": difficulty,
            "language": "es",
            "group": group,
            "rationale": rationale,
        },
    }
