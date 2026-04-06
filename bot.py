import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import os, time, hashlib, json, feedparser, requests
from datetime import datetime

# ===== KEEP ALIVE =====
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")
    def log_message(self, *args): pass

def server():
    HTTPServer(("0.0.0.0", 10000), Handler).serve_forever()

threading.Thread(target=server, daemon=True).start()

# ===== ENV =====
TG_TOKEN = os.environ.get("TG_TOKEN")
TG_CHANNEL = os.environ.get("TG_CHANNEL")
GEM_KEY = os.environ.get("GEM_KEY")

SEEN_FILE = "seen.json"
CHECK_INTERVAL = 600

RSS = [
    "https://feeds.reuters.com/reuters/worldNews",
    "https://feeds.bbci.co.uk/news/world/rss.xml"
]

# ===== SEEN =====
def load_seen():
    if os.path.exists(SEEN_FILE):
        return set(json.load(open(SEEN_FILE)))
    return set()

def save_seen(s):
    json.dump(list(s)[-500:], open(SEEN_FILE,"w"))

# ===== TRANSLATE =====
def translate(title, summary):
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEM_KEY}"
        prompt = f"O'zbek tiliga tarjima qil:\n{title}\n{summary[:300]}"
        body = {"contents":[{"parts":[{"text":prompt}]}]}
        r = requests.post(url,json=body,timeout=10)
        return r.json()["candidates"][0]["content"]["parts"][0]["text"]
    except:
        return f"{title}\n\n{summary[:150]}..."

# ===== TELEGRAM =====
def send(msg):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    requests.post(url,json={"chat_id":TG_CHANNEL,"text":msg})

# ===== WEATHER =====
def weather():
    try:
        r = requests.get("https://api.open-meteo.com/v1/forecast?latitude=41.3&longitude=69.2&current_weather=true")
        temp = r.json()["current_weather"]["temperature"]
        return f"🌤 Toshkent: {temp}°C"
    except:
        return "🌤 Ob-havo mavjud emas"

# ===== CURRENCY =====
def currency():
    try:
        r = requests.get("https://open.er-api.com/v6/latest/USD")
        uzs = r.json()["rates"]["UZS"]
        return f"💰 $1 = {int(uzs)} so‘m"
    except:
        return "💰 Valyuta mavjud emas"

# ===== DAILY =====
def daily():
    return f"{weather()}\n{currency()}\n\n📰 Bugungi yangiliklar kuzatib boring"

# ===== MAIN =====
def run():
    seen = load_seen()
    last_day = ""

    while True:
        now = datetime.now().strftime("%Y-%m-%d")

        # DAILY POST
        if now != last_day and datetime.now().hour == 9:
            send(daily())
            last_day = now

        # NEWS
        for url in RSS:
            feed = feedparser.parse(url)
            for e in feed.entries[:5]:
                link = e.link
                h = hashlib.md5(link.encode()).hexdigest()
                if h in seen: continue

                title = e.title
                summary = e.summary if "summary" in e else ""

                text = translate(title, summary)
                msg = f"📰 {text}\n\n🔗 {link}"
                send(msg)

                seen.add(h)
                time.sleep(3)

        save_seen(seen)
        time.sleep(CHECK_INTERVAL)

# ===== START =====
if __name__ == "__main__":
    send("✅ BOT ISHLAYAPTI")
    run()
