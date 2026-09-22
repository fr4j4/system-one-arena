from .business import BUSINESS
from .games import CATALOG

SCENARIOS = [
    {"id": key, "name": name, "category": cat, "description": desc, "kind": kind}
    for kind, entries in [("game", CATALOG), ("business", BUSINESS)]
    for key, name, cat, desc in entries
]
