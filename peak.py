#!/usr/bin/env python3
TELEGRAM_TOKEN = "8651873326:AAGrZW6u21sXdq38JU_Y0ccD7MS1u2WdFoQ"
TELEGRAM_CHAT_ID = "113146661"

def send_telegram(text):
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json={"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"}, timeout=10)
    except: pass
"""peak.py v0.5 — Cross-platform event detector with deduplication and scoring."""
import requests, sqlite3, xml.etree.ElementTree as ET, time, json
from datetime import datetime, timedelta

DB_NAME, REPORT_PATH = "peak.db", "peak_report.html"
USER_AGENT = "Mozilla/5.0"

STOP_WORDS = {
    "the","a","an","is","in","on","of","to","for","and","or","but","with","at","by","from",
    "his","her","its","our","your","their","has","have","been","are","was","were","be",
    "it","this","that","not","no","he","she","they","we","you","all","can","will","just",
    "like","about","over","more","new","what","when","who","how","after","into","than",
    "then","them","would","could","should","may","also","some","any","one","two","out",
    "up","back","team","match","game","club","play","player","season","league","national",
    "football","soccer","sport","wins","win","lose","beat","says","said","report","reports",
    "amid","watch","first","last","year","week","day","time","people","world","state",
    "house","official","officials","government","president","minister",
}


def check_telegram_updates():
    """Check if user sent /peak command and respond."""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
        resp = requests.get(url, timeout=10).json()
        if resp.get("ok") and resp.get("result"):
            last_update = resp["result"][-1]
            msg = last_update.get("message", {})
            text = msg.get("text", "")
            chat_id = str(msg.get("chat", {}).get("id", ""))
            if text == "/peak" and chat_id == TELEGRAM_CHAT_ID:
                return True
    except:
        pass
    return False

def fetch_hackernews():
    try:
        ids = requests.get("https://hacker-news.firebaseio.com/v0/topstories.json", timeout=10).json()[:30]
        titles = []
        for sid in ids:
            try:
                s = requests.get(f"https://hacker-news.firebaseio.com/v0/item/{sid}.json", timeout=8).json()
                if s and "title" in s: titles.append(s["title"])
            except: continue
        print(f"  ✓ Hacker News:  {len(titles)} stories")
        return titles
    except Exception as e:
        print(f"  ✗ Hacker News:  {e}")
        return []

def fetch_reddit_rss():
    subs = ["worldnews","news","technology","science","politics","business","environment"]
    titles = []
    for sub in subs:
        try:
            resp = requests.get(f"https://www.reddit.com/r/{sub}/.rss", headers={"User-Agent": USER_AGENT}, timeout=10)
            for item in ET.fromstring(resp.text).iter("item"):
                t = item.find("title")
                if t is not None and t.text: titles.append(t.text.strip())
        except Exception as e: print(f"  ⚠  Reddit r/{sub}: {e}")
        time.sleep(1)
    print(f"  ✓ Reddit RSS:   {len(titles)} posts")
    return titles

def fetch_news_rss():
    sources = [
        ("NPR","https://feeds.npr.org/1001/rss.xml"), ("Al Jazeera","https://www.aljazeera.com/xml/rss/all.xml"),
        ("NYT World","https://rss.nytimes.com/services/xml/rss/nyt/World.xml"), ("ABC News","https://abcnews.go.com/abcnews/topstories"),
        ("CBS News","https://www.cbsnews.com/latest/rss/main"), ("NBC News","https://feeds.nbcnews.com/nbcnews/public/world"),
        ("CNN","http://rss.cnn.com/rss/edition.rss"),
    ]
    titles = []
    for name, url in sources:
        try:
            resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=12)
            for item in ET.fromstring(resp.text).iter("item"):
                t = item.find("title")
                if t is not None and t.text: titles.append(t.text.strip())
        except Exception as e: print(f"  ⚠  {name}: {e}")
    print(f"  ✓ News RSS:     {len(titles)} headlines ({len(sources)} outlets)")
    return titles


def fetch_gdelt():
    """GDELT global news — free, no key, updates every 15 min."""
    try:
        url = "https://api.gdeltproject.org/api/v2/doc/doc?query=world&mode=artlist&maxrecords=50&format=json"
        resp = requests.get(url, timeout=15).json()
        titles = [a["title"] for a in resp.get("articles", []) if "title" in a]
        print(f"  ✓ GDELT:        {len(titles)} articles")
        return titles
    except Exception as e:
        print(f"  ✗ GDELT:        {e}")
        return []

def fetch_techmeme():
    """Techmeme RSS — clustered tech news."""
    try:
        resp = requests.get("https://www.techmeme.com/feed.xml", headers={"User-Agent": USER_AGENT}, timeout=15)
        root = ET.fromstring(resp.text)
        titles = []
        for item in root.iter("item"):
            t = item.find("title")
            if t is not None and t.text:
                titles.append(t.text.strip())
        print(f"  ✓ Techmeme:     {len(titles)} stories")
        return titles
    except Exception as e:
        print(f"  ✗ Techmeme:     {e}")
        return []

def fetch_memeorandum():
    """Memeorandum RSS — clustered political news."""
    try:
        resp = requests.get("https://www.memeorandum.com/feed.xml", headers={"User-Agent": USER_AGENT}, timeout=15)
        root = ET.fromstring(resp.text)
        titles = []
        for item in root.iter("item"):
            t = item.find("title")
            if t is not None and t.text:
                titles.append(t.text.strip())
        print(f"  ✓ Memeorandum:  {len(titles)} stories")
        return titles
    except Exception as e:
        print(f"  ✗ Memeorandum:  {e}")
        return []


def fetch_youtube_rss():
    """YouTube RSS feeds from major news channels."""
    channels = [
        ("BBC News", "https://www.youtube.com/feeds/videos.xml?channel_id=UCYfdidRxbB8Qhf0Nx7ioOYw"),
        ("CNN", "https://www.youtube.com/feeds/videos.xml?channel_id=UCupvZG-5ko_eiXAupbDfxWw"),
        ("Sky News", "https://www.youtube.com/feeds/videos.xml?channel_id=UCGSJ8YQ4qB3Nf4cL9k9sX2Q"),
        ("Reuters", "https://www.youtube.com/feeds/videos.xml?channel_id=UChqUTb7kYRX8-EiaN3XFrSQ"),
    ]
    titles = []
    for name, url in channels:
        try:
            resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=15)
            ns = "{http://www.w3.org/2005/Atom}"
            root = ET.fromstring(resp.text)
            for entry in root.iter(f"{ns}entry"):
                t = entry.find(f"{ns}title")
                if t is not None and t.text:
                    titles.append(t.text.strip())
        except Exception as e:
            print(f"  ⚠  YT {name}: {e}")
    print(f"  ✓ YouTube RSS:  {len(titles)} videos")
    return titles

def fetch_producthunt():
    """Product Hunt RSS — tech product launches."""
    try:
        resp = requests.get("https://www.producthunt.com/feed", headers={"User-Agent": USER_AGENT}, timeout=15)
        root = ET.fromstring(resp.text)
        titles = []
        for item in root.iter("item"):
            t = item.find("title")
            if t is not None and t.text:
                titles.append(t.text.strip())
        if not titles:
            for item in root.iter("{http://www.w3.org/2005/Atom}entry"):
                t = item.find("{http://www.w3.org/2005/Atom}title")
                if t is not None and t.text:
                    titles.append(t.text.strip())
        print(f"  ✓ Product Hunt: {len(titles)} products")
        return titles
    except Exception as e:
        print(f"  ✗ Product Hunt: {e}")
        return []

def fetch_dw():
    """Deutsche Welle RSS — European/global news."""
    try:
        resp = requests.get("https://rss.dw.com/rdf/rss-en-all", headers={"User-Agent": USER_AGENT}, timeout=15)
        root = ET.fromstring(resp.text)
        titles = []
        for item in root.iter("item"):
            t = item.find("title")
            if t is not None and t.text:
                titles.append(t.text.strip())
        print(f"  ✓ DW:           {len(titles)} headlines")
        return titles
    except Exception as e:
        print(f"  ✗ DW:           {e}")
        return []

def fetch_wikipedia():
    noise = {"main page","special:","wikipedia:","portal:","help:","template:","mediawiki:","talk:","file:","index.php"}
    try:
        y = (datetime.now() - timedelta(days=1)).strftime("%Y/%m/%d")
        resp = requests.get(f"https://wikimedia.org/api/rest_v1/metrics/pageviews/top/en.wikipedia/all-access/{y}", headers={"User-Agent": USER_AGENT}, timeout=15)
        articles = resp.json()["items"][0]["articles"][:150]
        result = [(a["article"].replace("_"," "), a["views"], a["rank"]) for a in articles if not any(a["article"].lower().startswith(n) for n in noise)]
        print(f"  ✓ Wikipedia:    {len(result)} articles")
        return result
    except Exception as e:
        print(f"  ✗ Wikipedia:    {e}")
        return []

def keywords(text):
    return {w.strip("'\".,!?-()") for w in text.lower().replace("_"," ").split() if len(w)>=4 and w not in STOP_WORDS}

def match(t1, t2, min_common=2):
    k1, k2 = keywords(t1), keywords(t2)
    return bool(k1 and k2) and len(k1 & k2) >= min_common

def cluster_and_score(raw_hits):
    groups = {}
    for hit in raw_hits:
        placed = False
        for existing in list(groups.keys()):
            if match(hit["canonical"], existing, 2):
                groups[existing]["sources"].add(hit["source"])
                groups[existing]["evidence"].append(f"{hit['source']}: {hit['evidence'][:100]}")
                placed = True
                break
        if not placed:
            groups[hit["canonical"]] = {"sources":{hit["source"]}, "evidence":[f"{hit['source']}: {hit['evidence'][:100]}"]}
    events = []
    for canon, data in groups.items():
        sc = len(data["sources"])
        if sc < 2: continue
        score = sc + (1 if sc>=3 else 0) + (1 if sc==4 else 0)
        events.append({"canonical":canon,"sources":sorted(data["sources"]),"source_count":sc,"score":score,"evidence":data["evidence"]})
    return sorted(events, key=lambda x: x["score"], reverse=True)

def init_db():
    conn = sqlite3.connect(DB_NAME)
    conn.execute("CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, canonical TEXT, score REAL, src_count INTEGER, sources TEXT, evidence TEXT)")
    conn.commit()
    return conn

def save_events(conn, events):
    ts = datetime.now().isoformat()
    for e in events:
        conn.execute("INSERT INTO events (ts, canonical, score, src_count, sources, evidence) VALUES (?, ?, ?, ?, ?, ?)", (ts, e["canonical"], e["score"], e["source_count"], ", ".join(e["sources"]), "\n".join(e["evidence"])))
    conn.commit()

def bar(score, mx=6):
    return "█"*min(score,mx) + "░"*(mx-min(score,mx))

def html(events):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    cols = {"hackernews":"#f97316","reddit":"#ef4444","news":"#3b82f6","wikipedia":"#22c55e"}
    cards = ""
    for i, e in enumerate(events, 1):
        badges = "".join(f'<span style="background:{cols.get(s,"#666")};color:#fff;padding:2px 10px;border-radius:20px;font-size:12px;margin-right:4px">{s}</span>' for s in e["sources"])
        ev = "".join(f'<div style="color:#777;font-size:12px;margin-top:4px">· {l}</div>' for l in e["evidence"][:6])
        cards += f"""<div style="background:#1a1a1a;border-radius:12px;padding:20px;margin:14px 0;border-left:4px solid #ff6b35;">
<div style="display:flex;align-items:baseline;gap:12px;margin-bottom:10px"><span style="font-size:28px;font-weight:700;color:#ff6b35">{i}</span><span style="font-size:17px;font-weight:600">{e['canonical']}</span></div>
<div style="margin-bottom:8px">{badges}</div>
<div style="font-family:monospace;color:#ff6b35;letter-spacing:2px;margin-bottom:8px">{bar(e['score'])} <span style="color:#555;font-size:12px;margin-left:8px">score {e['score']} · {e['source_count']} sources</span></div>
{ev}</div>"""
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Peak — {now}</title></head>
<body style="font-family:-apple-system,sans-serif;max-width:820px;margin:0 auto;padding:2rem;background:#111;color:#eee">
<div style="border-bottom:1px solid #222;padding-bottom:1rem;margin-bottom:1.5rem"><span style="font-size:28px;font-weight:600;letter-spacing:-1px">pe<span style="color:#ff6b35">a</span>k</span><span style="color:#444;font-size:13px;margin-left:12px">{len(events)} events · {now}</span></div>
{cards if events else '<div style="color:#555;text-align:center;padding:3rem">No cross-platform events detected.</div>'}
</body></html>"""

def main():
    print("\n"+"═"*52+"\n  Peak Detector v0.5\n"+"═"*52+"\n")
    hn = fetch_hackernews()
    red = fetch_reddit_rss()
    news = fetch_news_rss()
    youtube_titles = fetch_youtube_rss()
    producthunt_titles = fetch_producthunt()
    dw_titles = fetch_dw()
    gdelt_titles = fetch_gdelt()
    techmeme_titles = fetch_techmeme()
    memeorandum_titles = fetch_memeorandum()
    wiki_d = fetch_wikipedia()
    wiki = [a[0] for a in wiki_d]
    all_s = {"hackernews":hn,"reddit":red,"news":news,"gdelt":gdelt_titles, "techmeme":techmeme_titles, "memeorandum":memeorandum_titles, "youtube":youtube_titles, "producthunt":producthunt_titles, "dw":dw_titles, "wikipedia":wiki}
    print("\nMatching across all source pairs...")
    raw = []
    for i, a in enumerate(list(all_s.keys())):
        for b in list(all_s.keys())[i+1:]:
            mk = 3 if "wikipedia" in (a,b) else 2
            for ta in all_s[a]:
                for tb in all_s[b]:
                    if match(ta, tb, mk):
                        raw.append({"canonical":ta,"source":a,"evidence":ta})
                        raw.append({"canonical":ta,"source":b,"evidence":tb})
                        break
    events = cluster_and_score(raw)
    conn = init_db()
    save_events(conn, events)
    conn.close()
    print(f"\n{'═'*52}\n  CROSS-PLATFORM PEAKS — {len(events)} found\n{'═'*52}\n")
    for i, e in enumerate(events, 1):
        print(f"  #{i:02d} [{bar(e['score'])}] score {e['score']}  |  {e['canonical'][:80]}")
        print(f"       Sources: {' + '.join(e['sources'])}")
        print()
    with open(REPORT_PATH, "w", encoding="utf-8") as f: f.write(html(events))

    if events:
        msg_lines = ["🔴 <b>Peak — Top Events</b>\n"]
        for i, e in enumerate(events[:3], 1):
            msg_lines.append(f"{i}. [{e['score']}] {e['canonical'][:80]}")
        send_telegram("\n".join(msg_lines))

    print(f"  Report saved → {REPORT_PATH}\n")

    if events and events[0]["score"] >= 2:
        top = events[0]
        msg = "🔴 <b>Peak Alert</b>\n\n" + str(top["score"]) + " | " + top["canonical"] + "\nSources: " + ", ".join(top["sources"])
        send_telegram(msg)
if __name__ == "__main__": main()
