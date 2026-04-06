import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import os
import time
import hashlib
import json
import feedparser
import requests
from datetime import datetime
from pytz import timezone

# =======================
# Config
# =======================
TG_TOKEN = os.environ.get("TG_TOKEN")
TG_CHANNEL = os.environ.get("TG_CHANNEL")
GEM_KEY = os.environ.get("GEM_KEY")
CHECK_INTERVAL = 300  # yangiliklarni tekshirish (5 daqiqa)
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
    "iran", "hamas", "hezbollah", "sudan", "myanmar", "yemen",
    "economy", "finance", "stock", "currency", "inflation", "market",
    "politics", "government", "election", "policy", "law"
]

CITY = "Tashkent"  # ob-havo shahri
CURRENCY = ["USD", "EUR", "RUB"]  # valyutalar
OBHAVA_API = os.environ.get("OBHAVA_API")  # OpenWeatherMap API key

# =======================
# Simple Web Server for Render
# =======================
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot ishlayapti!")
    def log_message(self, *args):
        pass

def start_server():
    port = int(os.environ.get("PORT", 10000))
    HTTPServer(("0.0.0.0", port), Handler).serve_forever()

threading.Thread(target=start_server, daemon=True).start()

# =======================
# Seen Articles
# =======================
def load_seen():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r") as f:
            return set(json.load(f))
    return set()

def save_seen(seen):
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen)[-500:], f)

# =======================
# Helpers
# =======================
def is_war_news(title, summary=""):
    text = (title + " " + summary).lower()
    return any(kw in text for kw in WAR_KEYWORDS)

def translate_to_uzbek(title, summary, source):
    try:
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
    except Exception as e:
        print(f"Gemini API xato: {e}")
        return f"{title}\n{summary[:200]}...\nManba: {source}"

def send_to_telegram(text):
    try:
        url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
        payload = {"chat_id": TG_CHANNEL, "text": text, "disable_web_page_preview": False}
        resp = requests.post(url, json=payload, timeout=10)
        return resp.ok
    except Exception as e:
        print(f"Telegram xato: {e}")
        return False

# =======================
# Ob-havo va valyuta
# =======================
def send_morning_update():
    # Ob-havo
    try:
        w_url = f"http://api.openweathermap.org/data/2.5/weather?q={CITY}&appid={OBHAVA_API}&units=metric"
        w_data = requests.get(w_url, timeout=10).json()
        weather_msg = f"🌤 Ob-havo {CITY}:\nTemperatura: {w_data['main']['temp']}°C\nHavo: {w_data['weather'][0]['description']}"
    except:
        weather_msg = f"🌤 Ob-havo {CITY} ma'lumot topilmadi."

    # Valyuta
    try:
        c_msg = "💱 Valyuta kurslari:\n"
        for cur in CURRENCY:
            r = requests.get(f"https://api.exchangerate.host/latest?base=UZS&symbols={cur}", timeout=10).json()
            c_msg += f"{cur}: {r['rates'][cur]:.2f}\n"
    except:
        c_msg += "Ma'lumot topilmadi."

    send_to_telegram(f"☀️ Ertalabgi yangiliklar:\n\n{weather_msg}\n\n{c_msg}")

# =======================
# Main Bot Loop
# =======================
def run():
    print("Bot ishga tushdi!")
    seen = load_seen()
    last_morning = None
    while True:
        now = datetime.now(timezone('Asia/Tashkent'))
        # Har kuni ertalab 08:00
        if now.hour == 8 and (last_morning != now.date()):
            send_morning_update()
            last_morning = now.date()

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
