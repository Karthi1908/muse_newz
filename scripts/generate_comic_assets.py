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

COMIC_PREFIX = (
    "Classic 19th-century Victorian newspaper editorial satirical comic illustration, "
    "Punch magazine style woodcut engraving, monochrome etching on warm newsprint, high contrast crosshatching: "
)

COMICS_TO_GENERATE = [
    {
        "filename": "comic_mechanical_muse.png",
        "title": "The Mechanical Muse & The Editor's Magnifying Glass",
        "prompt": (
            f"{COMIC_PREFIX}Humorous satirical scene in a Victorian newspaper pressroom. "
            f"An eccentric editor with monocle and waistcoat examines a comical brass steampunk automaton typesetter "
            f"seated at an antique printing desk. The automaton holds a massive quill pen and points proudly to a stack of "
            f"verified broadsheet proofs. Ink bottles, scrolls, and gears in background, fine detailed woodcut comic panel."
        ),
    },
    {
        "filename": "comic_hallucination_trap.png",
        "title": "The Hallucination Trap: Fact-Checker and the Mechanical Owl",
        "prompt": (
            f"{COMIC_PREFIX}Humorous Victorian editorial cartoon. A stern fact-checker with spectacles and folio ledger "
            f"catches a mischievous winged automaton in a butterfly net made of primary source citations. "
            f"A wise mechanical owl wearing mortarboard perched atop a dictionary looks on approvingly. "
            f"Satirical 19th-century engraving caricature style, warm newsprint texture."
        ),
    },
]

async def main():
    if not settings.MODEL_API_KEY:
        print("ERROR: MODEL_API_KEY not configured.")
        return

    cache_dir = Path("data/demo_cache/images")
    cache_dir.mkdir(parents=True, exist_ok=True)
    static_comic_dir = Path("app/static/images/comics")
    static_comic_dir.mkdir(parents=True, exist_ok=True)

    headers = {
        "Authorization": f"Bearer {settings.MODEL_API_KEY}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=90.0) as client:
        for item in COMICS_TO_GENERATE:
            print(f"Generating comic: {item['filename']}...")
            payload = {
                "model": settings.MUSE_IMAGE_MODEL,
                "prompt": item["prompt"],
            }
            try:
                resp = await client.post(settings.image_generations_url, headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()
                b64 = data["data"][0]["b64_json"]
                img_bytes = base64.b64decode(b64)

                # Save to cache and static
                (cache_dir / item["filename"]).write_bytes(img_bytes)
                (static_comic_dir / item["filename"]).write_bytes(img_bytes)

                json_name = Path(item["filename"]).stem + ".json"
                (cache_dir / json_name).write_text(json.dumps({
                    "title": item["title"],
                    "topic": "Satirical Editorial Comic",
                    "b64_json": b64,
                    "data_uri": f"data:image/png;base64,{b64}",
                }), encoding="utf-8")

                print(f"SAVED: {item['filename']} ({len(img_bytes)} bytes)")
            except Exception as e:
                print(f"FAILED {item['filename']}: {e}")

if __name__ == "__main__":
    asyncio.run(main())

