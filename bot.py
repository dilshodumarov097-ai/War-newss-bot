import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import os
import time
import hashlib
import json
import feedparser
import requests
from datetime import datetime, timedelta, timezone

# =======================
# TIMEZONE (Toshkent UTC+5)
# =======================
UZ_TIMEZONE = timezone(timedelta(hours=5))

# =======================
# CONFIG
# =======================
TG_TOKEN = os.environ.get("TG_TOKEN")
TG_CHANNEL = os.environ.get("TG_CHANNEL")
GEM_KEY = os.environ.get("GEM_KEY")

CHECK_INTERVAL = 300
SEEN_FILE = "seen_articles.json"

RSS_FEEDS = [
    {"name": "Reuters", "url": "https://feeds.reuters.com/reuters/worldNews"},
    {"name": "BBC World", "url": "https://feeds.bbci.co.uk/news/world/rss.xml"},
    {"name": "Al Jazeera", "url": "https://www.aljazeera.com/xml/rss/all.xml"},
]

KEYWORDS = [
    "war","conflict","attack","missile","military","battle",
    "economy","finance","market","inflation",
    "politics","government","election"
]

# =======================
# WEB SERVER (Render)
# =======================
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")
    def log_message(self, *args): pass

def start_server():
    port = int(os.environ.get("PORT", 10000))
    HTTPServer(("0.0.0.0", port), Handler).serve_forever()

threading.Thread(target=start_server, daemon=True).start()

# =======================
# SEEN
# =======================
def load_seen():
    if os.path.exists(SEEN_FILE):
        return set(json.load(open(SEEN_FILE)))
    return set()

def save_seen(seen):
    json.dump(list(seen)[-500:], open(SEEN_FILE, "w"))

# =======================
# FILTER
# =======================
def is_relevant(title, summary):
    text = (title + summary).lower()
    return any(k in text for k in KEYWORDS)

# =======================
# TRANSLATE
# =======================
def translate(title, summary, source):
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEM_KEY}"
        prompt = f"""O'zbek tiliga tarjima qil:

📰 {title}
{summary[:300]}

Manba: {source}"""
        body = {"contents":[{"parts":[{"text":prompt}]}]}
        r = requests.post(url,json=body,timeout=10)
        return r.json()["candidates"][0]["content"]["parts"][0]["text"]
    except:
        return f"📰 {title}\n\n{summary[:150]}...\n\nManba: {source}"

# =======================
# TELEGRAM
# =======================
def send(msg):
    try:
        url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
        requests.post(url,json={"chat_id":TG_CHANNEL,"text":msg})
    except:
        pass

# =======================
# WEATHER + CURRENCY
# =======================
def morning_post():
    try:
        w = requests.get("https://api.open-meteo.com/v1/forecast?latitude=41.3&longitude=69.2&current_weather=true").json()
        temp = w["current_weather"]["temperature"]
    except:
        temp = "?"

    try:
        c = requests.get("https://open.er-api.com/v6/latest/USD").json()
        uzs = int(c["rates"]["UZS"])
    except:
        uzs = "?"

    msg = f"""🌅 Xayrli tong!

🌤 Toshkent: {temp}°C
💰 $1 = {uzs} so‘m

📰 Yangiliklar davom etadi..."""
    send(msg)

# =======================
# MAIN LOOP
# =======================
def run():
    seen = load_seen()
    last_morning = None

    while True:
        now = datetime.now(UZ_TIMEZONE)

        # Morning post 08:00
        if now.hour == 8 and last_morning != now.date():
            morning_post()
            last_morning = now.date()

        # NEWS
        for feed in RSS_FEEDS:
            try:
                f = feedparser.parse(feed["url"])
                for e in f.entries[:5]:
                    link = e.link
                    h = hashlib.md5(link.encode()).hexdigest()
                    if h in seen: continue

                    title = e.title
                    summary = e.get("summary","")

                    if not is_relevant(title, summary): continue

                    text = translate(title, summary, feed["name"])
                    send(text + "\n\n🔗 " + link)

                    seen.add(h)
                    time.sleep(2)

            except Exception as e:
                print("Feed error:", e)

        save_seen(seen)
        time.sleep(CHECK_INTERVAL)

# =======================
# START
# =======================
if __name__ == "__main__":
    send("✅ BOT ISHLADI")
    run()
