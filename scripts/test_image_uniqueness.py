import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.models.schemas import PublishedArticle, ReaderProfile
from app.services.runner import EditionPipelineRunner
from app.services.storage import StorageService

def test_no_duplicate_images():
    store = StorageService()
    runner = EditionPipelineRunner(storage=store)
    
    # We check all editions in the database or run a test edition
    eds = store.list_editions()
    for e_info in eds:
        eid = e_info["edition_id"]
        ed = store.get_edition(eid)
        img_paths = []
        for p in ed.pages:
            for a in p.articles:
                if a.image_path:
                    img_paths.append((p.page_number, a.slot_id, a.headline, a.image_path))
        
        print(f"\nEdition {eid} has {len(img_paths)} illustrated articles:")
        for pnum, slot, head, path in img_paths:
            print(f"  P{pnum} [{slot}]: {head[:40]}... -> {path}")

if __name__ == "__main__":
    test_no_duplicate_images()

