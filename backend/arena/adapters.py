"""Adapters isolate SDKs, secrets, limits and provider-specific result shapes."""

from __future__ import annotations

import asyncio
import multiprocessing as mp
import os
import time
from concurrent.futures import ProcessPoolExecutor

from arena.protocol import normalize


class Adapter:
    id = "base"

    def capabilities(self):
        return {
            "id": self.id,
            "types": ["choice", "ordinal", "boolean_probability"],
            "probabilities": True,
            "internal_timings": False,
        }

    async def warmup(self):
        return {"ready": True}

    async def decide(self, request):
        raise NotImplementedError

    async def close(self):
        pass


_AGENT = None
_FORWARD = {}


def _load_laya():
    global _AGENT
    if _AGENT is None:
        os.environ["USE_TF"] = "0"
        import laya
        import torch

        checkpoint = os.getenv("LAYA_CHECKPOINT", "multilingual")
        if checkpoint not in ("english", "multilingual", "typed-decisions"):
            raise ValueError("LAYA_CHECKPOINT: english, multilingual or typed-decisions")
        device = os.getenv("LAYA_DEVICE", "cpu")
        if device == "cuda" and not torch.cuda.is_available():
            raise ValueError("CUDA requested but unavailable; choose CPU explicitly or fix the GPU runtime")
        torch.set_num_threads(max(1, int(os.getenv("LAYA_CPU_THREADS", "4"))))
        _AGENT = laya.load(
            os.getenv("LAYA_MODEL_PATH", "convaiinnovations/laya"),
            device=device,
            subfolder=None if checkpoint == "english" else checkpoint,
        )
        if os.getenv("LAYA_MAX_LEN"):
            _AGENT.cfg["max_len"] = int(os.environ["LAYA_MAX_LEN"])
        if os.getenv("LAYA_HEAD_MAX_LEN"):
            _AGENT.cfg["head_max_len"] = int(os.environ["LAYA_HEAD_MAX_LEN"])

        def pre_hook(module, args):
            if _AGENT.device.type == "cuda":
                torch.cuda.synchronize()
            _FORWARD["start"] = time.perf_counter()

        def post_hook(module, args, result):
            if _AGENT.device.type == "cuda":
                torch.cuda.synchronize()
            _FORWARD["ms"] = (time.perf_counter() - _FORWARD["start"]) * 1000

        _AGENT.model.register_forward_pre_hook(pre_hook)
        _AGENT.model.register_forward_hook(post_hook)
    return _AGENT


def _check_laya_budget(agent, state, questions):
    from laya.common import render_options, serialize_state

    tok = agent.tok
    maximum, head_max = agent.cfg.get("max_len", 512), agent.cfg.get("head_max_len", 192)

    def tokens(s):
        return tok(s.replace(tok.mask_token, " "), add_special_tokens=False)["input_ids"]

    st = tokens(serialize_state(state))
    for key, q in questions.items():
        internal = agent._to_internal(q)
        opts = [len(tokens(" " + s)) for s in render_options(internal)]
        head = len(tokens(f"{internal['t']} question: {internal['ins']}"))
        option_tokens = sum(n + 1 for n in opts)
        if any(n > 48 for n in opts) or head_max - option_tokens < 16 or head > head_max - option_tokens:
            raise ValueError(
                f"{key}: option/instruction token budget exceeded; shorten schema or increase LAYA_HEAD_MAX_LEN"
            )
        if 4 + head + option_tokens + len(st) > maximum:
            raise ValueError(f"{key}: state token budget exceeded; shorten state or configure LAYA_MAX_LEN")


def _laya_call(payload=None):
    start = time.perf_counter()
    agent = _load_laya()
    if payload is None:
        agent.predict(
            {"text": "Hello"}, {"greeting": {"type": "noul", "instructions": "Is this a greeting?"}}
        )
        import torch

        return {
            "ready": True,
            "device": str(agent.device),
            "checkpoint": os.getenv("LAYA_CHECKPOINT", "multilingual"),
            "max_len": agent.cfg.get("max_len"),
            "head_max_len": agent.cfg.get("head_max_len"),
            "cold_start_ms": (time.perf_counter() - start) * 1000,
            "gpu": torch.cuda.get_device_name() if agent.device.type == "cuda" else None,
        }
    _check_laya_budget(agent, payload["state"], payload["questions"])
    prepared = time.perf_counter()
    raw = agent.predict(payload["state"], payload["questions"])
    raw["model"] = "laya/" + os.getenv("LAYA_CHECKPOINT", "multilingual")
    raw["arena_device"] = str(agent.device)
    requested = os.getenv("LAYA_DEVICE", "cpu")
    if requested == "cuda" and agent.device.type != "cuda":
        raise ValueError(
            "Laya fell back to CPU after a GPU failure; run rejected to avoid mixing hardware metrics"
        )
    total = (time.perf_counter() - start) * 1000
    raw["arena_timings"] = {
        "validation_ms": (prepared - start) * 1000,
        "inference_ms": _FORWARD.get("ms"),
        "local_predict_ms": total,
    }
    if agent.device.type == "cuda":
        import torch

        raw["arena_memory"] = {
            "allocated_bytes": torch.cuda.memory_allocated(),
            "reserved_bytes": torch.cuda.memory_reserved(),
        }
    return raw


class LayaAdapter(Adapter):
    id = "laya"

    def __init__(self):
        self.pool = None
        self.lock = asyncio.Lock()

    def capabilities(self):
        return {
            **super().capabilities(),
            "internal_timings": True,
            "resident": True,
            "checkpoint": os.getenv("LAYA_CHECKPOINT", "multilingual"),
        }

    def _pool(self):
        if os.getenv("LAYA_ENABLED", "false").lower() != "true":
            raise ValueError("Instala el extra laya y configura LAYA_ENABLED=true para cargar pesos locales")
        if self.pool is None:
            self.pool = ProcessPoolExecutor(max_workers=1, mp_context=mp.get_context("spawn"))
        return self.pool

    async def warmup(self):
        async with self.lock:
            return await asyncio.get_running_loop().run_in_executor(self._pool(), _laya_call)

    async def decide(self, request):
        # Semaphore waits belong to queue time, never to inference time.
        payload = {
            "state": request.state,
            "questions": {k: q.provider_dict() for k, q in request.questions.items()},
        }
        raw = await asyncio.get_running_loop().run_in_executor(self._pool(), _laya_call, payload)
        result = normalize(raw, request, "laya")
        result.timings = raw.pop("arena_timings", {})
        return result

    async def close(self):
        if self.pool:
            await asyncio.to_thread(self.pool.shutdown, wait=True, cancel_futures=True)
            self.pool = None
