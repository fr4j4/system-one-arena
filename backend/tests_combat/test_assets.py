import json
import struct
from pathlib import Path


def test_original_fighters_have_skins_animation_and_no_remote_uris():
    root = Path(__file__).resolve().parents[2] / "frontend/public/assets/combat/fighters"
    for name in ("ember", "flux", "terra", "nyx"):
        raw = (root / f"{name}.glb").read_bytes()
        magic, version, length = struct.unpack_from("<III", raw)
        assert magic == 0x46546C67 and version == 2 and length == len(raw)
        size, kind = struct.unpack_from("<II", raw, 12)
        assert kind == 0x4E4F534A
        data = json.loads(raw[20 : 20 + size])
        assert len(data["skins"][0]["joints"]) >= 16
        clips = {a["name"] for a in data["animations"]}
        assert {"idle", "walk", "light", "heavy", "charge", "beam", "ultimate", "finisher", "hurt"} <= clips
        assert len(clips) >= 25
        assert all("uri" not in b for b in data["buffers"])
        assert len(raw) < 1_000_000
