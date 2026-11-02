"""
Day-1 Live Verification Spike for Meta Muse Model API + Google ADK (Task T002 / Constitution §6).
Probes live https://api.meta.ai/v1 endpoints concurrently using MODEL_API_KEY from .env:
  1. GET  /models (discover exact model IDs)
  2. POST /chat/completions (verify MUSE_TEXT_MODEL & JSON output)
  3. POST /responses (verify search grounding support)
  4. POST /images/generations (verify MUSE_IMAGE_MODEL)
Never logs or prints the raw MODEL_API_KEY (Guardrail G-4.2).
"""
from __future__ import annotations
import asyncio
import json
import sys
from pathlib import Path
import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import settings


async def run_live_spike() -> dict:
    headers = {
        "Authorization": f"Bearer {settings.MODEL_API_KEY}",
        "Content-Type": "application/json",
    }
    results: dict = {
        "env_config": {
            "LLM_API_BASE_URL": settings.LLM_API_BASE_URL,
            "MUSE_TEXT_MODEL": settings.MUSE_TEXT_MODEL,
            "MUSE_IMAGE_MODEL": settings.MUSE_IMAGE_MODEL,
            "MUSE_VOICE_MODEL": settings.MUSE_VOICE_MODEL,
            "api_key_present": settings.has_live_api_key,
        },
        "live_probes": {},
    }

    async with httpx.AsyncClient(timeout=httpx.Timeout(25.0, connect=2.5)) as client:
        async def probe_models() -> tuple[str, dict]:
            try:
                r = await client.get(f"{settings.LLM_API_BASE_URL}/models", headers=headers)
                return "models_endpoint", {
                    "status_code": r.status_code,
                    "body": r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text[:400],
                }
            except Exception as exc:
                return "models_endpoint", {"error": f"{type(exc).__name__}: {exc}"}

        async def probe_chat() -> tuple[str, dict]:
            try:
                r = await client.post(
                    settings.chat_completions_url,
                    headers=headers,
                    json={
                        "model": settings.MUSE_TEXT_MODEL,
                        "temperature": 0.1,
                        "messages": [
                            {"role": "system", "content": "Reply with valid JSON: {\"status\": \"ok\", \"model_verified\": true}"},
                            {"role": "user", "content": "Verify connection for Your Daily Muse."},
                        ],
                    },
                )
                return "chat_completions", {
                    "status_code": r.status_code,
                    "body": r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text[:500],
                }
            except Exception as exc:
                return "chat_completions", {"error": f"{type(exc).__name__}: {exc}"}

        async def probe_responses() -> tuple[str, dict]:
            try:
                r = await client.post(
                    settings.responses_url,
                    headers=headers,
                    json={
                        "model": settings.MUSE_TEXT_MODEL,
                        "input": "Return 1 sentence on clean energy grid batteries.",
                    },
                )
                return "responses_endpoint", {
                    "status_code": r.status_code,
                    "body": r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text[:500],
                }
            except Exception as exc:
                return "responses_endpoint", {"error": f"{type(exc).__name__}: {exc}"}

        async def probe_images() -> tuple[str, dict]:
            try:
                r = await client.post(
                    settings.image_generations_url,
                    headers=headers,
                    json={
                        "model": settings.MUSE_IMAGE_MODEL,
                        "prompt": "Classic newspaper woodcut illustration of a printing press, monochrome ink",
                    },
                )
                img_body = r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text[:400]
                if isinstance(img_body, dict) and "data" in img_body:
                    img_body = {"data_count": len(img_body["data"]), "keys": list(img_body["data"][0].keys()) if img_body["data"] else []}
                return "images_generations", {
                    "status_code": r.status_code,
                    "body": img_body,
                }
            except Exception as exc:
                return "images_generations", {"error": f"{type(exc).__name__}: {exc}"}

        probe_list = await asyncio.gather(probe_models(), probe_chat(), probe_responses(), probe_images())
        for k, v in probe_list:
            results["live_probes"][k] = v

    return results


if __name__ == "__main__":
    out = asyncio.run(run_live_spike())
    print(json.dumps(out, indent=2))
