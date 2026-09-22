"""Versioned synthetic fixtures and editable decision DAGs; all actions are simulated."""

from __future__ import annotations

import copy

from arena.protocol import Question
from arena.scenarios.datasets import corpus

BUSINESS = [
    ("tickets", "Tickets de soporte", "Clasificación", "Equipo, prioridad y escalamiento"),
    ("email", "Bandeja de email", "Clasificación", "Intención y necesidad de respuesta"),
    ("spam", "Spam y phishing", "Filtros", "Probabilidades y falsos positivos"),
    ("moderation", "Moderación", "Filtros", "Permitir, revisar o bloquear mensajes"),
    ("events", "Flujo de eventos", "Filtros", "Relevancia y anomalías"),
    ("hierarchy", "Clasificación jerárquica", "Decisiones", "Clasificación plana o en dos niveles"),
    ("incidents", "Incidentes", "Priorización", "Impacto, severidad y responsables"),
    ("routing", "Enrutamiento de agentes", "Decisiones", "Seleccionar una herramienta simulada"),
    ("workflow", "Árbol de decisiones", "Workflows", "Preguntas, condiciones y rutas editables"),
]


def choice(instructions, options):
    return Question(type="choice", instructions=instructions, criteria=options)


def boolean(instructions):
    return Question(type="boolean_probability", instructions=instructions)


DEPARTMENT = {
    "billing": "Payments, invoices, refunds / pagos, facturación",
    "technical": "Bugs, outages / fallas técnicas",
    "sales": "Pricing, plans / ventas",
    "other": "Other / otros",
}
QUESTIONS = {
    "tickets": {
        "department": choice("Which department should handle this ticket?", DEPARTMENT),
        "priority": Question(
            type="ordinal",
            instructions="How urgent is this ticket?",
            criteria=["Routine request", "Needs attention soon", "Blocking outage or immediate deadline"],
        ),
        "escalate": boolean("Does the message report an outage affecting multiple users?"),
    },
    "email": {
        "intent": choice(
            "What is the sender's main intent?",
            {"request": "Asks for action", "information": "Shares information", "promotion": "Advertising"},
        ),
        "reply": boolean("Does the sender need a reply?"),
    },
    "spam": {
        "spam": boolean("Is this unsolicited promotional spam?"),
        "phishing": boolean(
            "Does this message attempt to steal credentials or trick the recipient into a fraudulent payment?"
        ),
    },
    "moderation": {
        "action": choice(
            "Classify this message for a public forum.",
            {
                "allow": "Ordinary civil conversation",
                "review": "Ambiguous or potentially abusive",
                "block": "Explicit personal abuse or threats",
            },
        )
    },
    "events": {
        "relevant": boolean("Does this event require an operator's attention?"),
        "anomaly": boolean("Does this event describe abnormal system behavior?"),
    },
    "hierarchy": {"category": choice("Choose the request category.", DEPARTMENT)},
    "incidents": {
        "severity": Question(
            type="ordinal",
            instructions="Rate operational incident severity.",
            criteria=["No service impact", "Partial degradation", "Complete outage"],
        ),
        "team": choice(
            "Which team owns this incident?",
            {
                "platform": "Infrastructure failures",
                "security": "Unauthorized access",
                "support": "User assistance",
            },
        ),
    },
    "routing": {
        "tool": choice(
            "Select a tool to handle the user request. Do not execute it.",
            {
                "search": "Find information",
                "calculator": "Compute arithmetic",
                "calendar": "Schedule an event",
                "human": "Escalate an ambiguous request",
            },
        )
    },
}

# Expected labels are stored alongside the input, never sent to a provider.
SAMPLES = {
    "tickets": [
        (
            "Nos cobraron dos veces. Necesito el reembolso de la factura.",
            {"department": "billing", "priority": 1, "escalate": 0},
        ),
        (
            "All users cannot sign in. Production is down right now.",
            {"department": "technical", "priority": 2, "escalate": 1},
        ),
        (
            "¿Cuánto cuesta el plan anual para cinco personas?",
            {"department": "sales", "priority": 0, "escalate": 0},
        ),
        (
            "Hola, necesito ayuda con mi cuenta, no sé qué ocurre.",
            {"department": ["other", "technical"], "priority": [0, 1], "escalate": 0},
        ),
    ],
    "email": [
        ("Please send the signed agreement before Friday.", {"intent": "request", "reply": 1}),
        (
            "Adjunto el resumen informativo de la semana. No se requiere respuesta.",
            {"intent": "information", "reply": 0},
        ),
        ("Limited offer! Buy our new shoes at 50% off.", {"intent": "promotion", "reply": 0}),
    ],
    "spam": [
        ("You won a million dollars! Send your password to claim now.", {"spam": 1, "phishing": 1}),
        ("Mañana nos reunimos a las 10. Saludos, Ana.", {"spam": 0, "phishing": 0}),
        ("Descuento exclusivo en zapatos. Compra ahora, oferta limitada.", {"spam": 1, "phishing": 0}),
        (
            "Soy tu banco: envía tu contraseña por email para evitar el bloqueo.",
            {"spam": [0, 1], "phishing": 1},
        ),
    ],
    "moderation": [
        ("No estoy de acuerdo, pero gracias por explicarlo.", {"action": "allow"}),
        ("You are an idiot and I will hurt you.", {"action": "block"}),
        ("Eso fue una tontería... o quizás entendí mal.", {"action": ["allow", "review"]}),
    ],
    "events": [
        (
            "Database error: replication lag 120 seconds, elevated failure rate.",
            {"relevant": 1, "anomaly": 1},
        ),
        ("Health check OK. CPU 12%. Scheduled backup completed.", {"relevant": 0, "anomaly": 0}),
        ("Error de autenticación: 900 intentos fallidos en un minuto.", {"relevant": 1, "anomaly": 1}),
    ],
    "hierarchy": [
        ("Duplicate invoice payment, please refund.", {"category": "billing", "subcategory": "refund"}),
        ("No puedo iniciar sesión, error al entrar.", {"category": "technical", "subcategory": "login"}),
        ("Quiero conocer el precio del plan enterprise.", {"category": "sales", "subcategory": "pricing"}),
    ],
    "incidents": [
        ("Production database offline, all users blocked.", {"severity": 2, "team": "platform"}),
        (
            "Unauthorized access found in an admin account; service remains available.",
            {"severity": 0, "team": "security"},
        ),
        ("Usuario solicita ayuda para actualizar su perfil.", {"severity": 0, "team": "support"}),
    ],
    "routing": [
        ("Calculate 19 times 43.", {"tool": "calculator"}),
        ("Agenda una reunión el lunes a las 9.", {"tool": "calendar"}),
        ("Find documentation about WebSocket.", {"tool": "search"}),
        ("Haz eso que te comenté antes.", {"tool": "human"}),
    ],
}

SUBCATEGORIES = {
    "billing": {"refund": "Refund or duplicate charge", "invoice": "Invoice question"},
    "technical": {"login": "Login or access problem", "outage": "Service outage"},
    "sales": {"pricing": "Pricing or plans", "contract": "Contract negotiation"},
    "other": {"general": "General question", "unknown": "Insufficient information"},
}


def default_graph(template="support"):
    q = QUESTIONS["tickets"]["department"].model_dump()
    if template == "email":
        return {
            "start": "phishing",
            "nodes": [
                {
                    "id": "phishing",
                    "kind": "question",
                    "question": QUESTIONS["spam"]["phishing"].model_dump(),
                    "next": "risk",
                },
                {
                    "id": "risk",
                    "kind": "condition",
                    "source": "phishing",
                    "operator": "gte",
                    "value": 0.7,
                    "yes": "review",
                    "no": "inbox",
                },
                {"id": "review", "kind": "output", "label": "Revisar"},
                {"id": "inbox", "kind": "output", "label": "Bandeja"},
            ],
        }
    if template == "incident":
        return {
            "start": "severity",
            "nodes": [
                {
                    "id": "severity",
                    "kind": "question",
                    "question": QUESTIONS["incidents"]["severity"].model_dump(),
                    "next": "critical",
                },
                {
                    "id": "critical",
                    "kind": "condition",
                    "source": "severity",
                    "operator": "gte",
                    "value": 1.5,
                    "yes": "oncall",
                    "no": "queue",
                },
                {"id": "oncall", "kind": "output", "label": "Guardia"},
                {"id": "queue", "kind": "output", "label": "Cola normal"},
            ],
        }
    return {
        "start": "department",
        "nodes": [
            {"id": "department", "kind": "question", "question": q, "next": "priority"},
            {
                "id": "priority",
                "kind": "question",
                "question": QUESTIONS["tickets"]["priority"].model_dump(),
                "next": "urgent",
            },
            {
                "id": "urgent",
                "kind": "condition",
                "source": "priority",
                "operator": "gte",
                "value": 1.5,
                "yes": "escalate",
                "no": "resolve",
            },
            {"id": "escalate", "kind": "output", "label": "Escalar al equipo"},
            {"id": "resolve", "kind": "output", "label": "Resolver en cola"},
        ],
    }


def validate_graph(graph):
    nodes = graph.get("nodes", [])
    if not 1 <= len(nodes) <= 50:
        raise ValueError("El árbol debe tener entre 1 y 50 nodos")
    by_id = {n["id"]: n for n in nodes}
    if len(by_id) != len(nodes) or graph.get("start") not in by_id:
        raise ValueError("IDs duplicados o nodo inicial inexistente")
    visiting, visited = set(), set()

    def walk(key, available):
        if key not in by_id:
            raise ValueError(f"Nodo inexistente: {key}")
        if key in visiting:
            raise ValueError("El árbol contiene un ciclo")
        visiting.add(key)
        visited.add(key)
        n = by_id[key]
        kind = n.get("kind")
        if kind == "question":
            Question.model_validate(n["question"])
            walk(n["next"], available | {key})
        elif kind == "condition":
            if n.get("source") not in available or n.get("operator") not in ("eq", "gte", "lt"):
                raise ValueError("La condición debe depender de una pregunta anterior")
            source_type = by_id[n["source"]]["question"]["type"]
            if n["operator"] != "eq" and (
                source_type == "choice" or not isinstance(n.get("value"), (int, float))
            ):
                raise ValueError("Los umbrales requieren preguntas numéricas")
            walk(n["yes"], available)
            walk(n["no"], available)
        elif kind == "output":
            if not n.get("label"):
                raise ValueError("La salida requiere una etiqueta")
        else:
            raise ValueError("Tipo de nodo desconocido")
        visiting.remove(key)

    walk(graph["start"], set())
    if len(visited) != len(nodes):
        raise ValueError("Hay nodos sin conexión desde el inicio")
    return graph


def fixtures(name):
    name = "tickets" if name == "workflow" else name
    if name in ("tickets", "email", "spam"):
        return corpus(name)
    return [
        {
            "id": f"{name}-{i}",
            "state": {"text": text},
            "expected": expected,
            "metadata": {
                "source": "Sintético · ejemplos iniciales",
                "version": "starter-v1",
                "difficulty": "claro",
            },
        }
        for i, (text, expected) in enumerate(SAMPLES[name])
    ]


def validate_dataset(items):
    if not isinstance(items, list) or not items or len(items) > 10000:
        raise ValueError("El dataset debe tener entre 1 y 10000 casos")
    ids = set()
    for index, item in enumerate(items):
        if not isinstance(item, dict) or not isinstance(item.get("state"), dict):
            raise ValueError("Cada caso requiere un objeto state")
        item.setdefault("id", f"import-{index + 1}")
        if not isinstance(item["id"], str) or item["id"] in ids:
            raise ValueError("Cada caso requiere un id de texto único")
        ids.add(item["id"])
        if not isinstance(item.get("metadata", {}), dict):
            raise ValueError("metadata debe ser un objeto")
        if not isinstance(item.get("expected", {}), dict):
            raise ValueError("expected debe ser un objeto")
    return items


class Business:
    def __init__(self, name, dataset=None, graph=None, options=None):
        self.name = name
        self.items = validate_dataset(copy.deepcopy(dataset or fixtures(name)))
        self.graph = validate_graph(graph or default_graph()) if name == "workflow" else None
        self.options = options or {}
        self.index = 0
        self.results = []
        self.answers = {}
        self.node = self.graph["start"] if self.graph else None
        self.path = []
        self.category = None
        self.done = False
        self.seq = 0
        self.item_latency_ms = 0.0
        self.item_calls = 0

    def observe(self):
        return {
            "scenario": self.name,
            **self.items[self.index]["state"],
            "index": self.index,
            "total": len(self.items),
            "done": self.done,
            "node": self.node,
            "path": self.path[:],
            "category": self.category,
        }

    def questions(self):
        if self.graph:
            n = next(n for n in self.graph["nodes"] if n["id"] == self.node)
            return {n["id"]: Question.model_validate(n["question"])}
        if self.name == "hierarchy":
            if self.options.get("hierarchy_mode") == "flat":
                return {
                    "subcategory": choice(
                        "Choose the specific category.",
                        {
                            f"{cat}/{sub}": desc
                            for cat, subs in SUBCATEGORIES.items()
                            for sub, desc in subs.items()
                        },
                    )
                }
            if self.category:
                return {"subcategory": choice("Choose the specific category.", SUBCATEGORIES[self.category])}
        return QUESTIONS[self.name]

    def apply(self, result):
        self.item_latency_ms += result.get("timings", {}).get("provider_ms", 0) or 0
        self.item_calls += 1
        values = {k: v["value"] for k, v in result["answers"].items()}
        self.answers.update(result["answers"])
        self.seq += 1
        if self.graph:
            nodes = {n["id"]: n for n in self.graph["nodes"]}
            self.path.append(self.node)
            self.node = nodes[self.node]["next"]
            while nodes[self.node]["kind"] != "question":
                n = nodes[self.node]
                self.path.append(self.node)
                if n["kind"] == "output":
                    self._finish_item(n["label"])
                    return
                value = self.answers[n["source"]]["value"]
                test = (
                    value == n["value"]
                    if n["operator"] == "eq"
                    else value >= n["value"]
                    if n["operator"] == "gte"
                    else value < n["value"]
                )
                self.node = n["yes"] if test else n["no"]
            return
        if self.name == "hierarchy" and not self.category and self.options.get("hierarchy_mode") != "flat":
            self.category = values["category"]
            return
        if self.name == "hierarchy" and self.options.get("hierarchy_mode") == "flat":
            cat, sub = values["subcategory"].split("/")
            self.answers["category"] = {
                "type": "choice",
                "value": cat,
                "probabilities": None,
                "confidence": None,
            }
            self.answers["subcategory"] = {**self.answers["subcategory"], "value": sub, "probabilities": None}
        self._finish_item()

    def fail(self, error, latency_ms=0):
        self.item_latency_ms += latency_ms
        self.item_calls += 1
        self.seq += 1
        self._finish_item(error=error)

    def _finish_item(self, output=None, error=None):
        self.results.append(
            {
                "id": self.items[self.index].get("id", str(self.index)),
                "metadata": self.items[self.index].get("metadata", {}),
                "status": "error" if error else "completed",
                "error": error,
                "latency_ms": round(self.item_latency_ms, 3),
                "calls": self.item_calls,
                "state": self.items[self.index]["state"],
                "answers": copy.deepcopy(self.answers),
                "expected": self.items[self.index].get("expected", {}),
                "path": self.path[:],
                "output": output,
            }
        )
        if self.index + 1 >= len(self.items):
            self.done = True
        else:
            self.index += 1
            self.answers, self.path, self.category = {}, [], None
            self.item_latency_ms, self.item_calls = 0.0, 0
            self.node = self.graph["start"] if self.graph else None
