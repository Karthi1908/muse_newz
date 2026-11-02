import asyncio
import base64
import hashlib
import json
import os
import sys
from pathlib import Path
import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import settings

HOUSE_STYLE_PREFIX = (
    "Classic broadsheet newspaper editorial woodcut and stipple ink illustration, "
    "monochrome etching on warm newsprint paper, high contrast crosshatching, no text: "
)

async def main():
    headline = "Phase II Epigenetic Reprogramming Trial Reports 31% Reversal in Corneal Endothelial Senescence Markers"
    topic = "Biotechnology & Longevity Medicine"
    prompt = (
        f"{HOUSE_STYLE_PREFIX}Ophthalmic cellular biology laboratory bench with specular microscope, "
        f"petri dishes with hexagonal corneal endothelial cells, mRNA lipid nanoparticle molecular model, "
        f"vintage medical engraving plate style"
    )
    headers = {
        "Authorization": f"Bearer {settings.MODEL_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.MUSE_IMAGE_MODEL,
        "prompt": prompt,
    }
    print(f"Generating image for {topic}...")
    async with httpx.AsyncClient(timeout=90.0) as client:
        resp = await client.post(settings.image_generations_url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
        b64 = data["data"][0]["b64_json"]
        img_bytes = base64.b64decode(b64)
        
        # Save to cache
        cache_dir = Path("data/demo_cache/images")
        cache_dir.mkdir(parents=True, exist_ok=True)
        
        key = hashlib.sha256(headline.strip().lower().encode("utf-8")).hexdigest()[:16]
        
        for name in [key, "biotech_corneal_reprogramming"]:
            (cache_dir / f"{name}.png").write_bytes(img_bytes)
            (cache_dir / f"{name}.json").write_text(json.dumps({
                "headline": headline,
                "topic": topic,
                "b64_json": b64,
                "data_uri": f"data:image/png;base64,{b64}",
            }), encoding="utf-8")
        print(f"SUCCESS: Saved biotech image ({len(img_bytes)} bytes) as {key}.png")

if __name__ == "__main__":
    asyncio.run(main())

