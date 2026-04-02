import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import os
import time
import hashlib
import json
import feedparser
import requests
from datetime import datetime

# ---------- Keep-alive server (Render uchun)
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

# ---------- Env variables
TG_TOKEN = os.environ.get("TG_TOKEN")
TG_CHANNEL = os.environ.get("TG_CHANNEL")
GEM_KEY = os.environ.get("GEM_KEY")

CHECK_INTERVAL = 300
SEEN_FILE = "seen_articles.json"

# ---------- RSS feeds
RSS_FEEDS = [
    {"name": "Reuters", "url": "https://feeds.reuters.com/reuters/worldNews"},
    {"name": "BBC", "url": "https://feeds.bbci.co.uk/news/world/rss.xml"},
    {"name": "The Guardian", "url": "https://www.theguardian.com/world/rss"},
    {"name": "Al Jazeera", "url": "https://www.aljazeera.com/xml/rss/all.xml"},
    {"name": "DW", "url": "https://rss.dw.com/xml/rss-en-world"},
]

KEYWORDS = [
    "war","conflict","attack","missile","military","troops","battle",
    "economy","inflation","oil","gas","sanctions","trade","market",
    "politics","government","president","election","law","nato",
    "ukraine","russia","china","usa","israel","gaza","iran"
]

# ---------- Seen articles
def load_seen():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r") as f:
            return set(json.load(f))
    return set()

def save_seen(seen):
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen)[-500:], f)

# ---------- Filter keywords
def is_relevant(title, summary):
    text = (title + " " + summary).lower()
    return any(k in text for k in KEYWORDS)

# ---------- Gemini translate
def translate(title, summary, source):
    if not GEM_KEY:
        return f"📰 {title}\n\n{summary[:200]}...\n\n🗺 {source}"

    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEM_KEY}"
        prompt = f"""
Quyidagini o'zbek tiliga tarjima qil.

📰 Sarlavha
Qisqa 2-3 gap

Manba: {source}

Title: {title}
Summary: {summary[:400]}
"""
        body = {"contents":[{"parts":[{"text":prompt}]}]}
        r = requests.post(url, json=body, timeout=15)
        data = r.json()
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()

    except Exception as e:
        print("Gemini xato:", e)
        return f"📰 {title}\n\n{summary[:200]}...\n\n🗺 {source}"

# ---------- Telegram send
def send(text):
    if not TG_TOKEN or not TG_CHANNEL:
        print("ENV variables yo‘q!")
        return False
    try:
        url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
        payload = {"chat_id": TG_CHANNEL, "text": text, "disable_web_page_preview": False}
        r = requests.post(url, json=payload, timeout=10)
        print("TG:", r.status_code)
        return r.ok
    except Exception as e:
        print("Telegram xato:", e)
        return False

# ---------- Main loop
def run():
    print("Bot ishga tushdi!")
    seen = load_seen()

    while True:
        new_articles = []

        for feed in RSS_FEEDS:
            try:
                data = feedparser.parse(feed["url"])
                for e in data.entries[:10]:
                    title = e.get("title","")
                    summary = e.get("summary","")
                    link = e.get("link","")
                    aid = hashlib.md5(link.encode()).hexdigest()
                    if aid in seen:
                        continue
                    if not is_relevant(title, summary):
                        continue
                    new_articles.append({
                        "id": aid,
                        "title": title,
                        "summary": summary,
                        "link": link,
                        "source": feed["name"]
                    })
                    seen.add(aid)
            except Exception as er:
                print("Feed xato:", er)

        print(f"Topildi: {len(new_articles)} yangi maqola")

        for a in new_articles:
            try:
                text = translate(a["title"], a["summary"], a["source"])
                msg = f"{text}\n\n🔗 {a['link']}"
                send(msg)
                time.sleep(3)
            except Exception as er:
                print("Send xato:", er)

        save_seen(seen)
        print("Kutish...", datetime.now())
        time.sleep(CHECK_INTERVAL)

# ---------- START
if __name__ == "__main__":
    send("✅ BOT ISHGA TUSHDI")
    run()
