import asyncio
import base64
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
from config.settings import settings

CACHE_DIR = settings.DATA_DIR / "demo_cache" / "images"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

ITEMS_TO_GENERATE = [
    {
        "key": "ad_muse_brief_press",
        "headline": "The Muse Newz: Morning Dispatch Edition",
        "topic": "House Advertisement",
        "prompt": "Classic vintage broadsheet newspaper woodcut advertisement, monochrome ink engraving, antique Gutenberg printing press with scrolls and heraldic banner, warm newsprint paper, fine crosshatching, ornate engraving style",
    },
    {
        "key": "ad_muse_brief_pocket",
        "headline": "The Muse Newz: 3-Minute Verification Digest",
        "topic": "House Advertisement",
        "prompt": "Classic vintage broadsheet newspaper woodcut advertisement, monochrome ink engraving, vintage pocket watch with Roman numerals beside folded newspaper and steam coffee cup, ornate woodcut corner filigree, newsprint texture",
    },
    {
        "key": "ad_muse_brief_owl",
        "headline": "The Muse Newz: The Fact-Checker's Emblem",
        "topic": "House Advertisement",
        "prompt": "Classic vintage broadsheet newspaper engraving emblem, wise classical owl perched on open ledger with scales of justice and quill pen, monochrome woodcut etching, warm newsprint paper",
    },
    {
        "key": "clean_energy_sodium_battery",
        "headline": "Sodium-Iron-Phosphate Grid Storage Batteries Reach Commercial Deployment Parity with Natural Gas Peakers",
        "topic": "Grid-Scale Clean Energy & Batteries",
        "prompt": "Classic broadsheet newspaper editorial woodcut and stipple ink illustration, monochrome etching on warm newsprint paper, high contrast crosshatching, no text: Industrial energy storage battery containers alongside high voltage transmission lines",
    },
    {
        "key": "space_laser_optical_mesh",
        "headline": "In-Orbit Optical Laser Mesh Transfers 1.6 Terabits Per Second Between Low-Earth and Geostationary Relays",
        "topic": "Space Launch & Orbital Infrastructure",
        "prompt": "Classic broadsheet newspaper editorial woodcut and stipple ink illustration, monochrome etching on warm newsprint paper, high contrast crosshatching, no text: Orbital satellites communicating via laser beam mesh above the Earth curve in woodcut style",
    },
    {
        "key": "hvdc_interconnector",
        "headline": "High-Voltage Direct Current Subsea Interconnector Links North Sea Wind Clusters to Alpine Pumped Hydro",
        "topic": "Grid-Scale Clean Energy & Batteries",
        "prompt": "Classic broadsheet newspaper editorial woodcut and stipple ink illustration, monochrome etching on warm newsprint paper, high contrast crosshatching, no text: Subsea high-voltage electrical cable being laid by engineering ship across stormy sea waters in woodcut engraving",
    },
]

def get_cache_key(headline: str) -> str:
    return hashlib.sha256(headline.strip().lower().encode("utf-8")).hexdigest()[:16]

async def generate_item(item: dict, client: httpx.AsyncClient):
    key = item.get("key")
    head_key = get_cache_key(item["headline"])
    
    # Save both by explicit key and headline hash
    png_path = CACHE_DIR / f"{key}.png"
    hash_png_path = CACHE_DIR / f"{head_key}.png"

    if png_path.exists() and hash_png_path.exists():
        print(f"Already cached: {item['headline'][:40]}", flush=True)
        return

    print(f"Generating image for: {item['headline'][:40]}...", flush=True)
    headers = {
        "Authorization": f"Bearer {settings.MODEL_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.MUSE_IMAGE_MODEL,
        "prompt": item["prompt"],
    }

    try:
        resp = await client.post(settings.image_generations_url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
        first = data["data"][0]
        if "b64_json" in first:
            b64_str = first["b64_json"]
            img_bytes = base64.b64decode(b64_str)
            
            # Save under named key
            png_path.write_bytes(img_bytes)
            (CACHE_DIR / f"{key}.json").write_text(json.dumps({
                "key": key,
                "headline": item["headline"],
                "topic": item["topic"],
                "b64_json": b64_str,
                "data_uri": f"data:image/png;base64,{b64_str}",
            }), encoding="utf-8")

            # Save under headline hash
            hash_png_path.write_bytes(img_bytes)
            (CACHE_DIR / f"{head_key}.json").write_text(json.dumps({
                "key": key,
                "headline": item["headline"],
                "topic": item["topic"],
                "b64_json": b64_str,
                "data_uri": f"data:image/png;base64,{b64_str}",
            }), encoding="utf-8")

            print(f"SAVED: {key}.png and {head_key}.png ({len(img_bytes)} bytes)", flush=True)
        else:
            print(f"No b64_json in response: {first.keys()}", flush=True)
    except Exception as exc:
        print(f"Error generating {item['headline'][:30]}: {exc}", flush=True)

async def main():
    async with httpx.AsyncClient(timeout=45.0) as client:
        for item in ITEMS_TO_GENERATE:
            await generate_item(item, client)
    print("ALL ASSETS GENERATED SUCCESSFULLY", flush=True)

if __name__ == "__main__":
    asyncio.run(main())

