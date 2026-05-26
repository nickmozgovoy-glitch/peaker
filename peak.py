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
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

def parse_pub_date(item_el):
    """Парсит pubDate из RSS элемента. Возвращает datetime или None."""
    for tag in ["pubDate", "dc:date", "published", "updated"]:
        el = item_el.find(tag)
        if el is None:
            # Попробовать с namespace
            for ns in ["{http://purl.org/dc/elements/1.1/}date",
                       "{http://www.w3.org/2005/Atom}published",
                       "{http://www.w3.org/2005/Atom}updated"]:
                el = item_el.find(ns)
                if el is not None:
                    break
        if el is not None and el.text:
            for fmt in ["%a, %d %b %Y %H:%M:%S %z",
                        "%a, %d %b %Y %H:%M:%S GMT",
                        "%Y-%m-%dT%H:%M:%S%z",
                        "%Y-%m-%dT%H:%M:%SZ"]:
                try:
                    return datetime.strptime(el.text.strip()[:31], fmt)
                except: continue
    return None

def age_hours(pub_dt):
    """Возраст публикации в часах. None если дата неизвестна."""
    if pub_dt is None:
        return None
    now = datetime.now(pub_dt.tzinfo) if pub_dt.tzinfo else datetime.now()
    return max(0, (now - pub_dt).total_seconds() / 3600)


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
    cached = get_cached("hackernews", 60)
    if cached:
        print(f"  ✓ Hacker News:  {len(cached)} stories (cached)")
        return cached
    try:
        ids = requests.get("https://hacker-news.firebaseio.com/v0/topstories.json", timeout=10).json()[:30]
        items = []
        for sid in ids:
            try:
                s = requests.get(f"https://hacker-news.firebaseio.com/v0/item/{sid}.json", timeout=8).json()
                if s and "title" in s:
                    url = s.get("url") or f"https://news.ycombinator.com/item?id={sid}"
                    items.append((s["title"], url))
            except: continue
        print(f"  ✓ Hacker News:  {len(items)} stories")
        return items
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
    cached = get_cached("news_rss", 60)
    if cached:
        print(f"  ✓ News RSS:     {len(cached)} headlines (cached)")
        return cached
    sources = [
        ("NPR","https://feeds.npr.org/1001/rss.xml"), ("Al Jazeera","https://www.aljazeera.com/xml/rss/all.xml"),
        ("NYT World","https://rss.nytimes.com/services/xml/rss/nyt/World.xml"), ("ABC News","https://abcnews.go.com/abcnews/topstories"),
        ("CBS News","https://www.cbsnews.com/latest/rss/main"), ("NBC News","https://feeds.nbcnews.com/nbcnews/public/world"),
        ("CNN","http://rss.cnn.com/rss/edition.rss"),
        # Unblocked via VPN — keep here; will timeout gracefully if VPN off
        ("BBC World", "http://feeds.bbci.co.uk/news/world/rss.xml"),
        ("The Guardian", "https://www.theguardian.com/world/rss"),
    ]
    items = []
    for name, url in sources:
        try:
            resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=12)
            for el in ET.fromstring(resp.text).iter("item"):
                t = el.find("title")
                link = el.find("link")
                if t is not None and t.text:
                    url_str = link.text.strip() if link is not None and link.text else ""
                    items.append((t.text.strip(), url_str))
        except Exception as e: print(f"  ⚠  {name}: {e}")
    print(f"  ✓ News RSS:     {len(items)} headlines ({len(sources)} outlets)")
    save_cache("news_rss", items)
    return items


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
    cached = get_cached("techmeme", 60)
    if cached:
        print(f"  ✓ Techmeme:     {len(cached)} stories (cached)")
        return cached
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
    cached = get_cached("memeorandum", 60)
    if cached:
        print(f"  ✓ Memeorandum:  {len(cached)} stories (cached)")
        return cached
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
    cached = get_cached("youtube_rss", 60)
    if cached:
        print(f"  ✓ YouTube RSS:  {len(cached)} videos (cached)")
        return cached
    """YouTube RSS feeds from major news channels. Returns list of (title, url)."""
    channels = [
        ("BBC News", "https://www.youtube.com/feeds/videos.xml?channel_id=UCYfdidRxbB8Qhf0Nx7ioOYw"),
        ("CNN", "https://www.youtube.com/feeds/videos.xml?channel_id=UCupvZG-5ko_eiXAupbDfxWw"),
        ("Sky News", "https://www.youtube.com/feeds/videos.xml?channel_id=UCGSJ8YQ4qB3Nf4cL9k9sX2Q"),
        ("Reuters", "https://www.youtube.com/feeds/videos.xml?channel_id=UChqUTb7kYRX8-EiaN3XFrSQ"),
    ]
    items = []
    for name, url in channels:
        try:
            resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=15)
            ns = "{http://www.w3.org/2005/Atom}"
            root = ET.fromstring(resp.text)
            for entry in root.iter(f"{ns}entry"):
                t = entry.find(f"{ns}title")
                link = entry.find(f"{ns}link")
                if t is not None and t.text:
                    video_url = link.get("href") if link is not None else ""
                    items.append((t.text.strip(), video_url))
        except Exception as e:
            print(f"  ⚠  YT {name}: {e}")
    print(f"  ✓ YouTube RSS:  {len(items)} videos")
    save_cache("youtube_rss", items)
    return items

def fetch_producthunt():
    cached = get_cached("producthunt", 60)
    if cached:
        print(f"  ✓ Product Hunt: {len(cached)} products (cached)")
        return cached
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


def fetch_wikipedia_anomalies():
    """
    Wikipedia Recent Changes anomaly detector.
    Returns article titles that are being edited by 3+ unique editors
    in the last 20 minutes — early signal of breaking news.
    """
    try:
        url = "https://en.wikipedia.org/w/api.php?action=query&list=recentchanges&rcnamespace=0&rclimit=100&rcprop=title|timestamp|user&format=json"
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=15)
        data = resp.json()
        changes = data.get("query", {}).get("recentchanges", [])
        if not changes:
            return []

        # Group by title and count unique editors
        from collections import defaultdict
        now = datetime.now()
        article_editors = defaultdict(set)

        for ch in changes:
            title = ch.get("title", "")
            user = ch.get("user", "")
            ts_str = ch.get("timestamp", "")
            if not title or not user:
                continue
            # Parse timestamp and check if within last 20 minutes
            try:
                ts = datetime.strptime(ts_str, "%Y-%m-%dT%H:%M:%SZ")
                age_minutes = (now - ts).total_seconds() / 60
                if age_minutes <= 20:
                    article_editors[title].add(user)
            except:
                continue

        # Filter: 3+ unique editors = anomaly
        anomalies = [title for title, editors in article_editors.items() if len(editors) >= 3]

        if anomalies:
            print(f"  ✓ Wiki Anomalies: {len(anomalies)} breaking signals")
        else:
            print(f"  ✓ Wiki Anomalies: 0 breaking signals (normal)")
        return anomalies
    except Exception as e:
        print(f"  ✗ Wiki Anomalies: {e}")
        return []

def fetch_wikipedia():
    cached = get_cached("wikipedia", 60)
    if cached:
        print(f"  ✓ Wikipedia:    {len(cached)} articles (cached)")
        return cached
    noise = {"main page","special:","wikipedia:","portal:","help:","template:","mediawiki:","talk:","file:","index.php"}
    try:
        y = (datetime.now() - timedelta(days=1)).strftime("%Y/%m/%d")
        resp = requests.get(f"https://wikimedia.org/api/rest_v1/metrics/pageviews/top/en.wikipedia/all-access/{y}", headers={"User-Agent": USER_AGENT}, timeout=15)
        articles = (resp.json().get("items") or [{}])[0].get("articles") or [][:150]
        result = [(a["article"].replace("_"," "), a["views"], a["rank"]) for a in articles if not any(a["article"].lower().startswith(n) for n in noise)]
        print(f"  ✓ Wikipedia:    {len(result)} articles")
        return result
    except Exception as e:
        print(f"  ✗ Wikipedia:    {e}")
        return []

def keywords(text):
    return {w.strip("'\".,!?-()") for w in text.lower().replace("_"," ").split() if len(w)>=4 and w not in STOP_WORDS}


# Слова которые встречаются >10% новостей и не могут быть единственной причиной матча
HIGH_FREQ_WORDS = {
    "trump","musk","elon","iran","russia","china","ukraine","israel","gaza",
    "biden","obama","putin","twitter","facebook","google","apple","tesla",
    "dogecoin","bitcoin","crypto","ethereum","war","peace","deal","talks",
    "election","vote","president","congress","senate","court","police","killed",
    "dead","dies","death","attack","shooting","fire","flood","crisis","market",
    "stock","dollar","tariff","trade","nuclear","missile","military","troops",
}

def is_meaningful_match(t1: str, t2: str) -> bool:
    """True если у текстов есть хотя бы одно нечастотное общее ключевое слово."""
    shared = keywords(t1) & keywords(t2)
    if not shared:
        return False
    # Если ВСЕ общие слова — высокочастотные → не склеиваем
    non_trivial = shared - HIGH_FREQ_WORDS
    return len(non_trivial) > 0


KNOWN_ENTITIES = {'twitter', 'taylor swift', 'ai', 'cuba', 'fortnite', 'apple', 'trump', 'google', 'mlb', 'china', 'cia', 'nsa', 'hamilton', 'amazon', 'putin', 'meta', 'eu', 'snapchat', 'roblox', 'reddit', 'pentagon', 'congress', 'microsoft', 'instagram', 'spacex', 'nadal', 'zelensky', 'israel', 'oscars', 'youtube', 'minecraft', 'ethereum', 'fed', 'djokovic', 'world cup', 'tiktok', 'nhl', 'netflix', 'olympics', 'modi', 'nasa', 'fbi', 'facebook', 'kanye', 'llm', 'nato', 'nba', 'nfl', 'beyonce', 'messi', 'ebola', 'chatgpt', 'biden', 'xi', 'emmy', 'covid', 'vaccine', 'drake', 'openai', 'russia', 'scholz', 'white house', 'climate', 'premier league', 'musk', 'taiwan', 'iran', 'tesla', 'senate', 'verstappen', 'bitcoin', 'rihanna', 'uk', 'fifa', 'gaza', 'macron', 'ukraine', 'gpt', 'serena', 'india', 'grammy', 'ronaldo', 'nvidia', 'imf', 'champions league', 'who', 'gta', 'un', 'germany', 'call of duty', 'supreme court', 'france', 'lebron'}

def entity_match(t1: str, t2: str) -> bool:
    """Форсировать матч, если есть общая известная сущность (без учёта регистра)."""
    k1 = {w.lower() for w in keywords(t1)}
    k2 = {w.lower() for w in keywords(t2)}
    shared = (k1 & k2) & KNOWN_ENTITIES
    return len(shared) >= 1

def match(t1, t2, min_common=2):
    """Два заголовка совпадают если имеют 2+ общих значимых ключевых слова."""
    k1, k2 = keywords(t1), keywords(t2)
    if not k1 or not k2:
        return False
    if len(k1 & k2) < min_common:
        return False
    # Дополнительная проверка: не склеивать по одним лишь высокочастотным словам
    return is_meaningful_match(t1, t2)


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
    """Сохранить события пропуская дубли за последние 2 часа."""
    ts = datetime.now().isoformat()
    saved = 0
    for e in events:
        # Проверяем: не было ли такого же canonical за последние 2 часа
        existing = conn.execute(
            """SELECT id FROM events
               WHERE canonical = ?
               AND ts > datetime('now', '-2 hours')
               LIMIT 1""",
            (e["canonical"],)
        ).fetchone()
        if existing:
            continue  # дубль — пропускаем
        conn.execute(
            "INSERT INTO events (ts,canonical,score,src_count,sources,evidence) "
            "VALUES(?,?,?,?,?,?)",
            (ts, e["canonical"], e["score"], e["source_count"],
             ", ".join(e["sources"]),
             str(e.get("evidence", "")))
        )
        saved += 1
    conn.commit()
    if saved < len(events):
        print(f"  ℹ  DB: {saved} новых, {len(events)-saved} дублей пропущено")

def bar(score, mx=6):
    return "█"*min(score,mx) + "░"*(mx-min(score,mx))

def html(events, url_map=None):
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
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><rect width=%22100%22 height=%22100%22 rx=%2220%22 fill=%22%23ff6b35%22/><text y=%22.75em%22 x=%22.5em%22 font-size=%2270%22 font-weight=%22bold%22 font-family=%22Arial%22 fill=%22%23fff%22>Λ</text></svg>"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Peak — {now}</title></head>
<body style="font-family:-apple-system,sans-serif;max-width:820px;margin:0 auto;padding:2rem;background:#111;color:#eee">
{cards if events else '<div style="color:#555;text-align:center;padding:3rem">No cross-platform events detected.</div>'}
</body></html>"""


def get_cached(source_name, max_age_min=90):
    try:
        conn = sqlite3.connect(DB_NAME)
        row = conn.execute('SELECT data, ts FROM source_cache WHERE source=? ORDER BY ts DESC LIMIT 1', (source_name,)).fetchone()
        conn.close()
        if row:
            age = (datetime.now() - datetime.fromisoformat(row[1])).total_seconds() / 60
            if age < max_age_min:
                data = json.loads(row[0])
                # Восстанавливаем кортежи, если они превратились в списки
                if data and isinstance(data[0], list):
                    data = [tuple(item) if isinstance(item, list) else item for item in data]
                return data
    except:
        pass
    return None

def save_cache(source_name, data):
    try:
        conn = sqlite3.connect(DB_NAME)
        conn.execute('CREATE TABLE IF NOT EXISTS source_cache (source TEXT, data TEXT, ts TEXT)')
        conn.execute('INSERT INTO source_cache (source, data, ts) VALUES (?, ?, ?)', (source_name, json.dumps(data), datetime.now().isoformat()))
        conn.commit()
        conn.close()
    except:
        pass


def build_inverted_index(sources_dict):
    """Строит инвертированный индекс: keyword -> [(source_name, title), ...]"""
    from collections import defaultdict
    index = defaultdict(list)
    for src_name, titles in sources_dict.items():
        for title in titles:
            # Приводим к строке на случай, если title — кортеж
            title_str = title[0] if isinstance(title, tuple) else title
            kws = keywords(title_str)
            for kw in kws:
                index[kw].append((src_name, title_str))
    return index

def main():
    print("\n"+"═"*52+"\n  Peak Detector v1.0\n"+"═"*52+"\n")
    hn_items = fetch_hackernews()
    hn = [t[0] if isinstance(t, tuple) else t for t in hn_items]
    red = []  # Reddit blocked
    news_items = fetch_news_rss()
    news = [t[0] if isinstance(t, tuple) else t for t in news_items]
    youtube_items = fetch_youtube_rss()
    youtube_titles = [t[0] if isinstance(t, tuple) else t for t in youtube_items]
    producthunt_items = fetch_producthunt()
    producthunt_titles = [t[0] if isinstance(t, tuple) else t for t in producthunt_items]
    dw_titles = []  # DW not working
    gdelt_titles = []  # GDELT disabled
    techmeme_titles = fetch_techmeme()
    memeorandum_titles = fetch_memeorandum()
    wiki_anomalies = fetch_wikipedia_anomalies()
    wiki_d = fetch_wikipedia()
    wiki = [a[0] for a in wiki_d]
    all_s = {"hackernews":hn,"reddit":red,"news":news,"techmeme":techmeme_titles, "memeorandum":memeorandum_titles, "youtube":youtube_titles, "producthunt":producthunt_titles, "wikipedia_anomalies":wiki_anomalies, "wikipedia":wiki}
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
        url_map = {}
    for src_items in [news_items, youtube_items, hn_items, producthunt_items]:
        try:
            for item in src_items:
                if isinstance(item, tuple) and len(item) > 1 and item[1]:
                    url_map[item[0]] = item[1]
        except: pass
    with open(REPORT_PATH, "w", encoding="utf-8") as f: f.write(html(events, url_map))

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
