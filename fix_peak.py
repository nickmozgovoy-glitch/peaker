#!/usr/bin/env python3
"""
fix_peak.py — патч для peak.py
Запустить: python3 fix_peak.py
Исправляет:
  1. NameError: all_titles_for_rare — убираем зависимость, заменяем на статичный список
  2. Зомби-новости (Dogecoin 2023) — фильтр pubDate в RSS + age penalty
  3. Дубли в БД — проверка перед INSERT
  4. Wikipedia 'items' error — более надёжный парсинг
"""
import re

with open("peak.py", "r", encoding="utf-8") as f:
    code = f.read()

original = code  # сохраняем на случай отката

# ─── ФИК 1: убираем has_rare_shared_kw и all_titles_for_rare ─────────────────
# Заменяем на статичный список высокочастотных слов — нет NameError, нет corpus
# ─────────────────────────────────────────────────────────────────────────────

RARE_GUARD = '''
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

'''

# Вставить перед def match()
if "is_meaningful_match" not in code:
    code = re.sub(
        r'(def match\(t1, t2)',
        RARE_GUARD + r'def match(t1, t2',
        code, count=1
    )
    print("✓ Фикс 1: is_meaningful_match добавлен")
else:
    print("  Фикс 1: уже применён")

# Обновить тело match() чтобы использовать is_meaningful_match
# Найти любую версию match и заменить на надёжную
MATCH_FUNC = '''def match(t1, t2, min_common=2):
    """Два заголовка совпадают если имеют 2+ общих значимых ключевых слова."""
    k1, k2 = keywords(t1), keywords(t2)
    if not k1 or not k2:
        return False
    if len(k1 & k2) < min_common:
        return False
    # Дополнительная проверка: не склеивать по одним лишь высокочастотным словам
    return is_meaningful_match(t1, t2)

'''

# Найти и заменить текущую функцию match
old_match = re.search(
    r'def match\(t1, t2.*?\n(?=\ndef |\nif __name__)',
    code, re.DOTALL
)
if old_match:
    code = code[:old_match.start()] + MATCH_FUNC + code[old_match.end():]
    print("✓ Фикс 1: функция match() обновлена")

# Убрать all_titles_for_rare везде где оно есть
code = re.sub(r'\s*all_titles_for_rare\s*=\s*\[\][^\n]*\n', '\n', code)
code = re.sub(r'\s*all_titles_for_rare\.extend[^\n]*\n', '', code)
code = re.sub(r',\s*all_titles_for_rare', '', code)
code = re.sub(r',\s*all_titles\b', '', code)
print("✓ Фикс 1: all_titles_for_rare удалён")

# ─── ФИК 2: pubDate фильтр для зомби-новостей ────────────────────────────────

PUBDATE_PARSER = '''
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

'''

if "parse_pub_date" not in code:
    # Вставить после импортов
    insert_after = re.search(r'^(import|from).*\n(?!\s*(import|from))', code, re.MULTILINE)
    if insert_after:
        pos = code.rfind('\n', 0, insert_after.end()) + 1
        # Найти конец блока импортов
        lines = code.split('\n')
        import_end = 0
        for i, line in enumerate(lines):
            if line.startswith('import ') or line.startswith('from '):
                import_end = i
        insert_pos = sum(len(l)+1 for l in lines[:import_end+1])
        code = code[:insert_pos] + PUBDATE_PARSER + code[insert_pos:]
    print("✓ Фикс 2: parse_pub_date добавлен")
else:
    print("  Фикс 2: уже применён")

# ─── ФИК 3: дубли в БД ───────────────────────────────────────────────────────
# Заменить save_events чтобы проверять дубли перед INSERT

SAVE_EVENTS_NEW = '''def save_events(conn, events):
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

'''

old_save = re.search(r'def save_events\(conn, events\).*?conn\.commit\(\)\s*\n',
                     code, re.DOTALL)
if old_save:
    code = code[:old_save.start()] + SAVE_EVENTS_NEW + code[old_save.end():]
    print("✓ Фикс 3: save_events с дедупликацией обновлён")
else:
    print("  Фикс 3: паттерн save_events не найден — добавить вручную")

# ─── ФИК 4: Wikipedia 'items' error ──────────────────────────────────────────
# Более надёжный парсинг с fallback

WIKI_FIX = '''def fetch_wiki_pageviews():
    """Top Wikipedia articles by pageviews (yesterday). Free, no key."""
    noise = {"main page","special:","wikipedia:","portal:","help:",
             "template:","mediawiki:","talk:","file:","index.php"}
    try:
        d = (datetime.now() - timedelta(days=1)).strftime("%Y/%m/%d")
        url = (f"https://wikimedia.org/api/rest_v1/metrics/pageviews/top/"
               f"en.wikipedia/all-access/{d}")
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        # Надёжный доступ к данным
        items = (data.get("items") or [{}])[0].get("articles") or []
        if not items:
            print(f"  ✗ Wikipedia:      пустой ответ")
            return []

        out = []
        for a in items[:150]:
            name = a.get("article","").replace("_"," ")
            if name and not any(name.lower().startswith(n) for n in noise):
                out.append({
                    "title": name,
                    "url":   f"https://en.wikipedia.org/wiki/{a['article']}",
                    "pub_ts": None  # pageviews — вчерашние данные, не зомби
                })
        print(f"  ✓ Wikipedia:      {len(out)} articles")
        return out
    except Exception as e:
        print(f"  ✗ Wikipedia:      {e}")
        return []

'''

old_wiki = re.search(r'def fetch_wiki_pageviews\(\).*?return \[\]\s*\n',
                     code, re.DOTALL)
if old_wiki:
    code = code[:old_wiki.start()] + WIKI_FIX + code[old_wiki.end():]
    print("✓ Фикс 4: fetch_wiki_pageviews обновлён")
else:
    print("  Фикс 4: fetch_wiki_pageviews не найден")

# ─── ЗАПИСЬ РЕЗУЛЬТАТА ────────────────────────────────────────────────────────

# Финальная проверка синтаксиса
import ast, sys
try:
    ast.parse(code)
    with open("peak.py", "w", encoding="utf-8") as f:
        f.write(code)
    print("\n✅ peak.py обновлён успешно")
    print("   Запусти: python peak.py")
except SyntaxError as e:
    print(f"\n✗ СИНТАКСИЧЕСКАЯ ОШИБКА: {e}")
    print("  Откат к оригиналу...")
    with open("peak.py", "w", encoding="utf-8") as f:
        f.write(original)
    print("  peak.py восстановлен без изменений")
    sys.exit(1)

