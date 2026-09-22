"""Jev quality benchmark: N short paired matches of a subject profile vs a baseline, in process.

Smoke without network: uv run --no-sync python scripts/bench_jev.py --provider baseline --seconds 8
"""

import argparse
import asyncio
import json
import tempfile
import time
from collections import Counter
from pathlib import Path

from arena.combat.profiles import Registry
from arena.combat.protocol import MatchConfig, Slot
from arena.combat.session import Match
from arena.metrics import percentiles
from arena.storage import Store
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
COUNTS = ("accepted", "completed", "applied", "expired", "rejected", "errors")


def plan(matches, characters):
    """Paired schedule like Series: each pair runs once per side; characters rotate per pair."""
    rows = []
    for k in range(matches):
        pair, mirror = divmod(k, 2)
        mine = characters[pair % len(characters)]
        theirs = characters[(pair + 1) % len(characters)]
        rows.append(dict(pair=pair, side=1 if mirror else 0, subject=mine, opponent=theirs))
    return rows


def winner(state, side):
    """Engine winner if decided, else round wins, else health lead at the time limit, subject's view."""
    if not state:
        return None
    w = state.get("winner")
    if w:
        return "subject" if w == f"p{side + 1}" else "opponent"
    a, b = state.get("wins") or (0, 0)
    if a == b:
        a, b = (f["health"] for f in state["fighters"])
    if a == b:
        return "draw"
    return "subject" if (a > b) == (side == 0) else "opponent"


async def run_match(args, registry, store, row):
    subject = Slot(fighter_id=row["subject"], model_profile_id=args.subject)
    opponent = Slot(fighter_id=row["opponent"], model_profile_id=args.opponent)
    config = MatchConfig(
        players=[opponent, subject] if row["side"] else [subject, opponent],
        max_seconds=args.seconds,
        pace=args.pace,
        seed=42 + row["pair"],
    )
    registry.validate(config)
    match = Match(config, registry, store)
    events = asyncio.Queue()
    match.subscribers.add(events)
    started = time.perf_counter()
    await match.start()
    while not match.task.done():
        await asyncio.sleep(0.25)
        if match.status == "paused":
            await match.stop()
    await match.task
    side = row["side"]
    pid = f"p{side + 1}"
    reasons = Counter()
    while not events.empty():
        e = events.get_nowait()
        if e["kind"] == "rejected" and e.get("player_id") == pid:
            reasons[e.get("reason") or "unknown"] += 1
    view = match.view()
    player = view["players"][side]
    stats = (view["state"] or {}).get("fighters", [{}, {}])[side].get("stats", {})
    return dict(
        **(row | dict(side=pid)),
        status=view["status"],
        error=view["error"],
        wall_seconds=round(time.perf_counter() - started, 2),
        active_seconds=view["active_seconds"],
        model=player["actual_model"],
        counts={k: player["counts"].get(k, 0) for k in COUNTS},
        rejected_by_reason=dict(reasons),
        latencies=list(match.stats[side]["latencies"]),
        damage_dealt=stats.get("damage", 0),
        damage_taken=stats.get("received", 0),
        winner=winner(view["state"], side),
    )


def summarize(rows):
    counts = Counter()
    reasons = Counter()
    latencies = []
    for r in rows:
        counts.update(r["counts"])
        reasons.update(r["rejected_by_reason"])
        latencies += r["latencies"]
        r["applied_rate"] = rate(r["counts"])
        r["latency"] = percentiles(r.pop("latencies"))
    return dict(
        matches=len(rows),
        counts=dict(counts),
        rejected_by_reason=dict(reasons),
        applied_rate=rate(counts),
        latency=percentiles(latencies),
        damage_dealt=sum(r["damage_dealt"] for r in rows),
        damage_taken=sum(r["damage_taken"] for r in rows),
        results=dict(Counter(r["winner"] for r in rows)),
        failed=sum(r["status"] not in ("completed",) for r in rows),
    )


def rate(counts):
    return round(counts["applied"] / counts["completed"], 3) if counts.get("completed") else None


def table(rows, total):
    head = f"{'#':>2} {'side':4} {'chars':12} {'req':>4} {'done':>4} {'appl':>4} {'exp':>4} {'rej':>4}"
    head += f" {'rate':>5} {'p50':>7} {'p95':>7} {'dmg+':>5} {'dmg-':>5} winner"
    lines = [head]
    for i, r in enumerate(rows, 1):
        c, lat = r["counts"], r["latency"]
        lines.append(
            f"{i:>2} {r['side']:4} {r['subject'] + '/' + r['opponent']:12} {c['accepted']:>4} {c['completed']:>4}"
            f" {c['applied']:>4} {c['expired']:>4} {c['rejected']:>4} {fmt(r['applied_rate']):>5}"
            f" {fmt(lat['p50']):>7} {fmt(lat['p95']):>7} {r['damage_dealt']:>5} {r['damage_taken']:>5}"
            f" {r['winner']}{'' if r['status'] == 'completed' else ' [' + r['status'] + ']'}"
        )
    c, lat = total["counts"], total["latency"]
    lines.append(
        f"{'all':>2} {'':4} {'':12} {c.get('accepted', 0):>4} {c.get('completed', 0):>4}"
        f" {c.get('applied', 0):>4} {c.get('expired', 0):>4} {c.get('rejected', 0):>4}"
        f" {fmt(total['applied_rate']):>5} {fmt(lat['p50']):>7} {fmt(lat['p95']):>7}"
        f" {total['damage_dealt']:>5} {total['damage_taken']:>5} {total['results']}"
    )
    lines.append(f"rejected by reason: {total['rejected_by_reason']}")
    return "\n".join(lines)


def fmt(v):
    return "-" if v is None else f"{v:g}"


def parse(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--provider", choices=("jev", "baseline"), default="jev")
    ap.add_argument(
        "--baseline-profile", default="reference", help="subject profile when --provider baseline"
    )
    ap.add_argument("--opponent", default="reference", help="baseline profile id for the other side")
    ap.add_argument("--matches", type=int, default=2)
    ap.add_argument("--seconds", type=int, default=20)
    ap.add_argument("--characters", default="ember,flux", help="comma list, rotated per pair")
    ap.add_argument("--pace", choices=("native", "equal_windows"), default="native")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args(argv)
    args.subject = "jev" if args.provider == "jev" else args.baseline_profile
    args.characters = [c.strip() for c in args.characters.split(",") if c.strip()]
    if args.out is None:
        args.out = ROOT / f"docs/combat/evidence/bench-{time.strftime('%Y%m%d-%H%M%S')}.json"
    return args


async def main(args):
    load_dotenv(ROOT / ".env")
    registry = Registry()
    if registry.profiles[args.opponent].public()["ai"]:
        raise SystemExit("--opponent must be a baseline profile (no AI)")
    store = Store(tempfile.mkdtemp(prefix="arena-bench-"))
    store.start()
    rows = []
    try:
        for row in plan(args.matches, args.characters):
            r = await run_match(args, registry, store, row)
            rows.append(r)
            print(f"match {len(rows)}/{args.matches}: {r['status']} {r['winner']}", flush=True)
    finally:
        await registry.close()
        await store.close()
    total = summarize(rows)
    report = dict(
        subject=args.subject,
        opponent=args.opponent,
        seconds=args.seconds,
        pace=args.pace,
        characters=args.characters,
        created_at=time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        total=total,
        matches=rows,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2))
    print(table(rows, total))
    print(f"wrote {args.out}")


def _selfcheck():
    p = plan(4, ["ember", "flux"])
    assert [(r["side"], r["subject"], r["opponent"]) for r in p] == [
        (0, "ember", "flux"),
        (1, "ember", "flux"),
        (0, "flux", "ember"),
        (1, "flux", "ember"),
    ]
    hp = lambda a, b: dict(winner=None, fighters=[dict(health=a), dict(health=b)])  # noqa: E731
    assert winner(hp(5, 3), 0) == "subject" and winner(hp(5, 3), 1) == "opponent"
    assert winner(hp(4, 4), 0) == "draw" and winner(dict(winner="p2"), 1) == "subject"
    assert winner(hp(5, 3) | dict(wins=[0, 1]), 0) == "opponent"  # round wins beat current health
    assert winner(hp(5, 3) | dict(wins=[1, 1]), 0) == "subject"
    assert rate(dict(applied=1, completed=4)) == 0.25 and rate(dict(completed=0)) is None


if __name__ == "__main__":
    _selfcheck()
    asyncio.run(main(parse()))
