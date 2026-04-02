if __name__ == "__main__":
    send_to_telegram("✅ TEST XABAR")  # BU YERGA
    run()
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot ishlayapti!")
    def log_message(self, *args):
        pass

def start_server():
    HTTPServer(("0.0.0.0", 10000), Handler).serve_forever()

threading.Thread(target=start_server, daemon=True).start()
import os
import time
import hashlib
import json
import feedparser
import requests
from datetime import datetime

TG_TOKEN = os.environ.get("TG_TOKEN")
TG_CHANNEL = os.environ.get("TG_CHANNEL")
GEM_KEY = os.environ.get("GEM_KEY")
CHECK_INTERVAL = 300
SEEN_FILE = "seen_articles.json"

RSS_FEEDS = [
    {"name": "Reuters", "url": "https://feeds.reuters.com/reuters/worldNews"},
    {"name": "BBC World", "url": "https://feeds.bbci.co.uk/news/world/rss.xml"},
    {"name": "The Guardian", "url": "https://www.theguardian.com/world/rss"},
    {"name": "Al Jazeera", "url": "https://www.aljazeera.com/xml/rss/all.xml"},
    {"name": "DW News", "url": "https://rss.dw.com/xml/rss-en-world"},
]

WAR_KEYWORDS = [
    "war", "conflict", "attack", "missile", "strike", "troops", "military",
    "battle", "killed", "wounded", "bombing", "invasion", "ceasefire",
    "ukraine", "russia", "gaza", "israel", "palestine", "nato", "weapons",
    "airstrike", "artillery", "casualties", "frontline", "offensive",
    "iran", "hamas", "hezbollah", "sudan", "myanmar", "yemen"
]

def load_seen():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r") as f:
            return set(json.load(f))
    return set()

def save_seen(seen):
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen)[-500:], f)

def is_war_news(title, summary=""):
    text = (title + " " + summary).lower()
    return any(kw in text for kw in WAR_KEYWORDS)

def translate_to_uzbek(title, summary, source):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEM_KEY}"
    prompt = f"""Quyidagi inglizcha yangilikni O'zbek tiliga tarjima qil.
Faqat tarjima qil, hech qanday izoh qo'shma.
Aynan shu formatda yoz:

📰 [sarlavha]

[qisqa mazmun 2-3 gap]

🗺 Manba: {source}

Sarlavha: {title}
Mazmun: {summary[:500] if summary else ''}"""
    body = {"contents": [{"parts": [{"text": prompt}]}]}
    resp = requests.post(url, json=body, timeout=15)
    data = resp.json()
    return data["candidates"][0]["content"]["parts"][0]["text"].strip()

def send_to_telegram(text):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = {"chat_id": TG_CHANNEL, "text": text, "disable_web_page_preview": False}
    resp = requests.post(url, json=payload, timeout=10)
    return resp.ok

def run():
    print("Bot ishga tushdi!")
    seen = load_seen()
    while True:
        new_articles = []
        for feed_info in RSS_FEEDS:
            try:
                feed = feedparser.parse(feed_info["url"])
                for entry in feed.entries[:10]:
                    title = entry.get("title", "")
                    summary = entry.get("summary", "")
                    link = entry.get("link", "")
                    article_id = hashlib.md5(link.encode()).hexdigest()
                    if article_id in seen:
                        continue
                    if not is_war_news(title, summary):
                        continue
                    new_articles.append({"id": article_id, "title": title, "summary": summary, "link": link, "source": feed_info["name"]})
                    seen.add(article_id)
            except Exception as e:
                print(f"Xato {feed_info['name']}: {e}")

        for article in new_articles:
            try:
                uzbek_text = translate_to_uzbek(article["title"], article["summary"], article["source"])
                full_message = f"{uzbek_text}\n\n🔗 {article['link']}"
                success = send_to_telegram(full_message)
                print(f"{'OK' if success else 'XATO'}: {article['title'][:60]}")
                time.sleep(3)
            except Exception as e:
                print(f"Yuborishda xato: {e}")

        save_seen(seen)
        print(f"Kutilmoqda... {datetime.now().strftime('%H:%M')}")
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    run()
send_to_telegram("✅ TEST XABAR")
