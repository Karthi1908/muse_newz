import json
from pathlib import Path

img_dir = Path("data/demo_cache/images")
for jf in sorted(img_dir.glob("*.json")):
    try:
        data = json.loads(jf.read_text(encoding="utf-8"))
        headline = data.get("headline", "")
        topic = data.get("topic", "")
        print(f"{jf.stem:<30} | {topic:<20} | {headline}")
    except Exception as e:
        print(f"{jf.stem}: error {e}")

