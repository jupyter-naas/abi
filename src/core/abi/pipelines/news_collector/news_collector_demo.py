# -------------------------------------------------------------
# 🧠 AI News Collector for ABI
# Author: Othmane
# Purpose: Fetch daily AI news (OpenAI & Anthropic),
#          store them in JSON format, and upload to Oxigraph
# -------------------------------------------------------------

import json
import feedparser     # used to read RSS feeds
import requests       # used to send data to Oxigraph
from rdflib import Graph, Literal, RDF, URIRef, Namespace
from datetime import datetime
import logging

# -------------------------------------------------------------
# 🪵 Logging setup — every run is saved in news_log.txt
# -------------------------------------------------------------
logging.basicConfig(
    filename="news_log.txt",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

# -------------------------------------------------------------
# STEP 1 — Define AI News Feeds
# -------------------------------------------------------------
feeds = {
    "OpenAI": "https://feeds.feedburner.com/TheOpenAI",
    "Anthropic": "https://news.ycombinator.com/rss"
}

# -------------------------------------------------------------
# STEP 2 — Fetch latest news from each feed
# -------------------------------------------------------------
def fetch_news():
    all_news = []
    for model, url in feeds.items():
        print(f"\n📰 Fetching news for {model}...")
        logging.info(f"Fetching news for {model}...")
        feed = feedparser.parse(url)

        if not feed.entries:
            print("⚠️  No news found for this source.")
            logging.warning(f"No news found for {model}")
            continue

        for entry in feed.entries[:5]:
            news_item = {
                "provider": model,
                "title": entry.title,
                "link": entry.link,
                "date": entry.get("published", datetime.now().strftime("%Y-%m-%d"))
            }
            all_news.append(news_item)

    print(f"\n✅ Collected {len(all_news)} news items in total.")
    logging.info(f"Collected {len(all_news)} total news items.")
    return all_news

# -------------------------------------------------------------
# STEP 3 — Save collected news to JSON file
# -------------------------------------------------------------
def save_to_json(news_data):
    with open("ai_news.json", "w", encoding="utf-8") as f:
        json.dump(news_data, f, indent=4, ensure_ascii=False)
    print("💾 News saved successfully to ai_news.json")
    logging.info("News saved locally to ai_news.json")

# -------------------------------------------------------------
# STEP 4 — Upload news to Oxigraph knowledge graph
# -------------------------------------------------------------
def upload_to_oxigraph(news_data):
    if not news_data:
        print("⚠️ No news to upload — skipping Oxigraph upload.")
        logging.warning("No news to upload — skipped Oxigraph upload.")
        return

    g = Graph()
    AI = Namespace("http://example.org/ai#")

    for item in news_data:
        news_uri = URIRef(item["link"])
        g.add((news_uri, RDF.type, AI.News))
        g.add((news_uri, AI.title, Literal(item["title"])))
        g.add((news_uri, AI.provider, Literal(item["provider"])))
        g.add((news_uri, AI.date, Literal(item["date"])))

    turtle_data = g.serialize(format="turtle")

    # Correct Oxigraph endpoint
    url = "http://localhost:7878/store?default"
    headers = {"Content-Type": "text/turtle"}

    try:
        resp = requests.post(url, headers=headers, data=turtle_data.encode("utf-8"))
        if resp.status_code in [200, 201, 204]:
            print("✅ Data uploaded successfully to Oxigraph!")
            logging.info(f"Upload successful: HTTP {resp.status_code}")
        else:
            print(f"❌ Upload failed: HTTP {resp.status_code}")
            logging.error(f"Upload failed: HTTP {resp.status_code} - {resp.text}")
    except requests.exceptions.RequestException as e:
        print(f"❌ Error connecting to Oxigraph: {e}")
        logging.error(f"Connection error to Oxigraph: {e}")

# -------------------------------------------------------------
# MAIN PROGRAM EXECUTION
# -------------------------------------------------------------
if __name__ == "__main__":
    logging.info("----- Script execution started -----")
    try:
        news_data = fetch_news()
        save_to_json(news_data)
        upload_to_oxigraph(news_data)
        logging.info("Script finished successfully.\n")
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        print(f"⚠️ Unexpected error: {e}")
