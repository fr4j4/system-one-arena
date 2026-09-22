"""Versioned gameplay data. Frame timings belong to the server, never animation clips."""

RULES_VERSION = "combat-1.0.0"
CONTENT_VERSION = "eclipse-1.0.0"
FPS = 60
FIGHTERS = {
    "ember": dict(
        name="Ember",
        title="El fuego interior",
        element="Fuego",
        color="#ff825c",
        role="Presión",
        description="Encadena golpes y rompe la distancia con fuego.",
        ultimate="Erupción solar",
        finisher="Fénix incandescente",
    ),
    "flux": dict(
        name="Flux",
        title="Más allá del relámpago",
        element="Electricidad",
        color="#66ddff",
        role="Movilidad",
        description="Cierra la distancia y castiga una apertura con velocidad.",
        ultimate="Ruptura eléctrica",
        finisher="Ascensión del trueno",
    ),
    "terra": dict(
        name="Terra",
        title="Voluntad inquebrantable",
        element="Tierra",
        color="#edca7b",
        role="Resistencia",
        description="Absorbe un impacto y responde con un golpe ascendente.",
        ultimate="Colapso tectónico",
        finisher="Pilar celestial",
    ),
    "nyx": dict(
        name="Nyx",
        title="El silencio del eclipse",
        element="Eclipse",
        color="#c0a1ff",
        role="Contraataque",
        description="Anticipa un golpe y convierte la defensa en una apertura.",
        ultimate="Eclipse",
        finisher="Fragmentación astral",
    ),
}
ARENAS = {
    "sanctuary": dict(name="Santuario del Eclipse", subtitle="Entre el cielo y la ceniza", color="#bd7c64"),
    "reactor": dict(name="Reactor Celeste", subtitle="El corazón de una estrella", color="#649fc2"),
}


def move(label, energy, damage, startup, active, recovery, reach, level="mid", guard=10, **kw):
    return dict(
        label=label,
        energy=energy,
        damage=damage,
        startup=startup,
        active=active,
        recovery=recovery,
        range=reach,
        level=level,
        guard=guard,
        **kw,
    )


MOVES = {
    "light": move("Golpe ligero", 0, 40, 6, 3, 12, 1200, guard=6),
    "heavy": move("Golpe fuerte", 0, 85, 14, 4, 24, 1800, guard=14),
    "low": move("Barrido bajo", 0, 55, 10, 3, 20, 1500, "low"),
    "overhead": move("Golpe elevado", 0, 75, 20, 4, 24, 1500, "overhead", 14),
    "launcher": move("Lanzador", 10, 65, 16, 3, 26, 1400, guard=16),
    "throw": move("Agarre", 0, 90, 12, 2, 28, 900, "throw"),
    "bolt": move("Proyectil", 15, 65, 18, 1, 20, 20000, "power", 12),
    "beam": move("Rayo de energía", 35, 140, 36, 24, 36, 20000, "power", 30),
    "ultimate": move("Técnica definitiva", 100, 340, 36, 6, 48, 2500, "ultimate", 60),
    "air_heavy": move("Patada aérea", 0, 70, 8, 4, 20, 1600, guard=12),
}
SIGNATURES = {
    "ember": move("Ráfaga ígnea", 25, 35, 18, 15, 30, 2000, guard=6, multi=3),
    "flux": move("Paso relámpago", 25, 90, 12, 3, 30, 1500, guard=16),
    "terra": move("Puño tectónico", 25, 110, 24, 4, 36, 1500, guard=20, armor=True),
    "nyx": move("Contra del eclipse", 25, 100, 6, 18, 30, 1800, guard=15, counter=True),
}
ROUTES = {
    "combo_pressure": dict(label="Presión", steps=["light", "light", "heavy"], energy=0),
    "combo_air": dict(label="Ascensión", steps=["light", "launcher", "air_heavy"], energy=10),
    "combo_power": dict(label="Convergencia", steps=["light", "heavy", "signature"], energy=25),
    "combo_chase": dict(label="Persecución", steps=["dash_forward", "light", "bolt"], energy=15),
}
ACTIONS = {
    "neutral": "Esperar",
    "forward": "Avanzar",
    "back": "Retroceder",
    "crouch": "Agacharse",
    "jump": "Saltar",
    "jump_forward": "Salto frontal",
    "jump_back": "Salto atrás",
    "dash_forward": "Dash frontal",
    "dash_back": "Dash atrás",
    "evade": "Evasión de energía",
    "guard_high": "Guardia alta",
    "guard_low": "Guardia baja",
    "charge": "Cargar energía",
    "break": "Escape de combo",
    "signature": "Técnica propia",
    "hold": "Sostener",
    "push": "Impulsar",
    "surge": "Sobrecargar",
    "yield": "Ceder",
    "finish": "Rematar",
    "spare": "Perdonar",
    **{k: v["label"] for k, v in MOVES.items()},
    **{k: v["label"] for k, v in ROUTES.items()},
}
PRESETS = {
    "finisher": "Remate cinematográfico",
    "neutral": "Encuentro libre",
    "close": "Distancia de combo",
    "defense": "Defensa y parry",
    "clash": "Choque de energía",
    "ultimate": "Energía máxima",
    "air": "Combate aéreo",
    "corner": "Salida de la esquina",
}


def catalog():
    return dict(
        rules_version=RULES_VERSION,
        content_version=CONTENT_VERSION,
        fighters=[dict(id=k, **v) for k, v in FIGHTERS.items()],
        arenas=[dict(id=k, **v) for k, v in ARENAS.items()],
        moves=MOVES,
        signatures=SIGNATURES,
        routes=ROUTES,
        actions=ACTIONS,
        presets=PRESETS,
    )
