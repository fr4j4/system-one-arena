import json

from arena.combat.profiles import Registry
from arena.combat.protocol import MatchConfig, Slot


async def test_profiles_share_resource_gate_without_sharing_model_identity(tmp_path, monkeypatch):
    path = tmp_path / "profiles.json"
    path.write_text(
        json.dumps(
            [
                {
                    "id": "jev-two",
                    "name": "Other Jev",
                    "provider": "jev",
                    "model": "another-version",
                    "endpoint": "https://api.typesafe.ai/v1/systemone",
                    "credential_env": "TYPESAFE_API_KEY",
                }
            ]
        )
    )
    monkeypatch.setenv("COMBAT_PROFILES_FILE", str(path))
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-not-a-real-key")
    registry = Registry()
    try:
        assert registry.gates["jev"] is registry.gates["jev-two"]
        assert registry.adapters["jev"].profile.model != registry.adapters["jev-two"].profile.model
        config = MatchConfig(
            players=[Slot(controller="baseline", model_profile_id="jev-two"), Slot(controller="model")]
        )
        registry.validate(config)
        assert [s.controller for s in config.players] == ["model", "baseline"]
        assert "test-not-a-real-key" not in json.dumps(registry.public())
        assert "credential_env" not in json.dumps(registry.public())
    finally:
        await registry.close()
