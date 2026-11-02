import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.storage import StorageService

s = StorageService()
eds = s.list_editions()
print(f"Total editions in archive: {len(eds)}")
for e_info in eds:
    eid = e_info["edition_id"]
    ed = s.get_edition(eid)
    print(f"\n=== Edition {eid} ({ed.format_label}) ===")
    for p in ed.pages:
        for a in p.articles:
            if a.image_path or a.image_data_uri:
                print(f"  Page {p.page_number} | Slot {a.slot_id} ({a.slot_kind}) [{a.topic}]:")
                print(f"    Headline: {a.headline}")
                print(f"    image_path: {a.image_path}")
                print(f"    image_caption: {a.image_caption}")
                print(f"    used_placeholder: {a.used_placeholder_image}")
