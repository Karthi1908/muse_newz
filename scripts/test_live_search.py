import asyncio
import urllib.parse
import xml.etree.ElementTree as ET
import html
import re
import httpx

def sanitize_untrusted_web_text(raw_text: str) -> str:
    no_tags = re.sub(r"<[^>]+>", " ", raw_text)
    cleaned = re.sub(r"\s+", " ", no_tags).strip()
    return html.unescape(cleaned)

async def test_live_search(topic: str = "crypto"):
    encoded = urllib.parse.quote(topic)
    url = f"https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/rss+xml, application/xml, text/xml",
    }
    print(f"Fetching live RSS for: {topic}...")
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
            print(f"Status: {resp.status_code}, Length: {len(resp.text)}")
            root = ET.fromstring(resp.text)
            items = root.findall(".//item")
            print(f"Found {len(items)} items:")
            for idx, item in enumerate(items[:5], 1):
                title = item.findtext("title", "")
                link = item.findtext("link", "")
                pub_date = item.findtext("pubDate", "")
                source_el = item.find("source")
                source_name = source_el.text if source_el is not None else "News Wire"
                
                # Split source from Google News title format "Headline - Source Name"
                clean_headline = title
                if " - " in title:
                    parts = title.rsplit(" - ", 1)
                    clean_headline = parts[0].strip()
                    if source_name == "News Wire":
                        source_name = parts[1].strip()

                print(f"\n[{idx}] {clean_headline}")
                print(f"    Source: {source_name} | Date: {pub_date}")
                print(f"    URL: {link[:60]}...")
    except Exception as e:
        print(f"Error fetching live RSS: {e}")

if __name__ == "__main__":
    asyncio.run(test_live_search("crypto"))

