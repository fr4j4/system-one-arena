# Combat v2 — approved implementation

The user approved the combat-only product on 2026-09-22. Preserve 8f228fb on legacy and arena-legacy-v1; implement on combat-v2, then merge to main. Do not overwrite legacy data or include secrets. New storage is data/combat-v2.

## Product
Four original anime-energy fighters (Ember, Flux, Terra, Nyx), two 3D arenas (Eclipse sanctuary and Celestial reactor), XY-only authoritative combat. Model/model, local human/model, training, tactical laboratory, paired series and replay. One local human per match; no online multiplayer or touch combat. Keyboard/gamepad remapping. Full original skinned characters and animations; non-gory cinematic finishers.

## Rules v1
60 ticks/s; X arena [-10,10], Y height, Z=0. Best-of 1/3/5 (default3), 90s rounds. KO or higher health wins; draws award no points, max best_of+2 rounds. Simultaneous hits resolve together. HP1000; energy25 initially, max100; guard100. Energy passive2/s idle/walk, charge12/s after15f; basic hit+3/heavy+5/received+2/parry+8 once per move; power hits do not generate energy. Guard regenerates20/s after60f free of block/hit; break stuns45f then guard50. Physical block no chip; power chip10% cannot KO.

Movement: walk forward/back, crouch, vertical/forward/back jump. Dash1.8u/12f cooldown30f, no invulnerability. Energy evade20E,8f invulnerability,cooldown90f. No grounded body crossing. High/low guard; overhead beats low, low beats high; throws beat both. Parry first6f of fresh guard,30f rearm; cannot parry beams/ultimates.

Moves energy/damage/startup-active-recovery/range:
light 0/40/6-3-12/1.2; heavy0/85/14-4-24/1.8; low0/55/10-3-20/1.5; overhead0/75/20-4-24/1.5; launcher10/65/16-3-26/1.4; throw0/90/12-2-28/.9; bolt15/65/18-1-20/travel; beam35/140/36-24-36/20; ultimate100/340/36-6-48/2.5; break50 once per combo, not throws/clash/cinematics.
Signatures25E: Ember3x35 range2 18-15-30; Flux dash1.8 and90 12-3-30 no body crossing; Terra110 range1.5 24-4-36 one-hit armor (still damage, no throws/ultimates); Nyx counter100 6-18-30 triggers middle/high physical only.
Combos: light-light-heavy; light-launcher-air_heavy; light-heavy-signature; dash-light-bolt. Input buffer6f; hit-confirmed cancel windows. Scale100/85/70/55/40%; max6 hits/3 aerial; knockdown then protected recovery. Costs per move, no refunds. Whiff/interruption/resource failure stops chain; blocked chain takes preauthorized brief guard.
Beam clash: 3 sealed simultaneous pulses800ms each; hold0E/1strength, push10/2, surge20/4 (consecutive surge2), yield takes40 knockback (both yield0). No response hold marked engine fallback. Winner damage min(200,140+8*margin); tie dissipates. Round clock suspended. Opponent choice hidden until pulse resolves.
After final KO: winner has3s choose finish/spare; finisher4–6s skip allowed, no cost or result changes; timeout normal victory. Ultimate cinema only on confirmed hit. Camera/VFX never own game rules.

## Architecture / protocol
Independent authoritative combat process and pure integer-scaled engine. Separate session coordinator, model profiles, observations, storage and rendering. Input WS seq+ack, server-assigned ticks; focus loss releases controls, human disconnect pauses. Snapshots30Hz, renderer interpolates. Replay stores command ticks, snapshots, rule/content/model versions; no model queries.
combat/1: public self/opponent/resources/positions/phase/current move timing/projectiles/walls/legal actions compact stats/recent4 relevant events. No private response, hidden clash choices, keys or graphics. Typed action choice incl approved combo route; no chain-of-thought. Same semantic observations across adapters. Laya tokenizer preflight, remove optional history first, never silent critical truncation.
Native 3Hz max/player, one physical call pending/player,800ms budget,1000ms age. Movement400ms/guard600ms/charge800ms holds. Routes execute chosen conditionals only. No queries when wait is only legal choice. Shared provider gates. Epoch invalidation on pause/round/clash/cinema/restart; immediate stop physics before draining physical calls. Three errors or5s no useful result pause with visible reason, no silent bot substitution. Equal-window evaluation800ms separate from native latency.
ModelProfile includes adapter+model/checkpoint+endpoint+server credential env ref; resolved profile immutable per match. Two profiles of same provider supported. Public API /api/v2 catalog/profiles/matches/controls/live/replays/series/training. Events tagged player,tick,source and decision correlation. Metrics damage/guard/parry/combo/energy/clash/latency/rejections. Paired series swap sides and fighters.

## Visual direction
Full-screen arena with fighter-select side panels, cinematic versus identity, dark blue-black/ivory, ember coral and flux cyan accents, restrained violet for Nyx and gold Terra. Barlow Condensed display, DM Sans body, IBM Plex Mono telemetry. Signature: opposing character selection plates framing live 3D arena. Inspector collapsible. No old scenario navigation. WebGL2, GLB skinned original humanoid rigs, toon bands/contours, state-driven animation, meaningful impact pauses, trails, auras, directional sound and adaptive music. Settings reduced flash/shake/motion and audio channels. High/medium/low quality; preload before paid calls; WebGL failure blocks start. Asset origins/licenses in manifest; use own generated geometry/animation plus verified CC0 where helpful, no paid dependency or runtime asset hotlinks. Target60FPS1080p, <=25MB selected match resources; mobile spectator/config only.

## Delivery checklist
- [x] 1 Legacy preserved/published, new combat shell/storage
- [x] 2 Pure engine, moves/resources/rounds, human/reference
- [x] 3 Profiles/model protocol/routing/observations/stop
- [x] 4 Combos/aerial/parry/escape/ultimate/clash
- [x] 5 Four skinned fighters/two arenas/finishers
- [x] 6 Visual/audio polish, controls, accessibility, quality
- [x] 7 Lab/series/replay/metrics/export
- [x] 8 Verification, documentation, main merge/push/server

## Verification
Engine tests costs/regen/bounds/timing/defense/projectiles/cancel/hit scaling/caps/KO/ties/mirrors/seeded replay. Runtime tests both players/shared gates/slow providers/late epochs/pause/stop/failures/sealed choices. API and browser full loops, keyboard/gamepad, focus/disconnect, slots/inspector/energy/clash/replay. Real Jev and Laya checks all special phases; do not claim checks not performed. Thirty minute soak, memory/renderer cleanup, measured performance/hardware, desktop/mobile screenshots and recording. Keys remain ignored. Every step gets meaningful checks and a commit; final app must include all steps, not just first slice.

Delivery verified on main: 74 Python tests, 6 browser tests, real provider checks, 1871s accumulated stability across two segments. Continuous 30min, hardware GPU60FPS and CUDA remain unverified; see docs/verification.md for measured limits.
