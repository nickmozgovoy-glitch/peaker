#!/usr/bin/env python3
"""Add clickable links to peak_report.html using data from peak sources."""
import re, sys
from peak import fetch_news_rss, fetch_hackernews, fetch_youtube_rss, fetch_producthunt

def build_url_map():
    url_map = {}
    for fetch_func in (fetch_news_rss, fetch_hackernews, fetch_youtube_rss, fetch_producthunt):
        try:
            items = fetch_func()
            for item in items:
                if isinstance(item, tuple) and len(item) > 1 and item[1]:
                    url_map[item[0]] = item[1]
        except Exception as e:
            print(f"Warning: {fetch_func.__name__} failed: {e}")
    print(f"URL map built: {len(url_map)} entries")
    return url_map

def linkify_html(url_map, html_path="peak_report.html"):
    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()

    def replace_match(match):
        prefix = match.group(1)  # · source: 
        title = match.group(2)   # title text
        suffix = match.group(3)  # </div>
        url = url_map.get(title.strip())
        if url:
            return f'{prefix}<a href="{url}" target="_blank" style="color:#3b82f6;text-decoration:none">{title}</a>{suffix}'
        else:
            return match.group(0)  # unchanged

    # Match exactly: <div style="color:#777;...">· source: title text</div>
    pattern = r'(<div style="color:#777;font-size:12px;margin-top:4px">· [^:]+: )(.+?)(</div>)'
    new_html = re.sub(pattern, replace_match, html)

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(new_html)
    
    # Count links
    link_count = new_html.count('href=')
    print(f"Links added: {link_count}")

if __name__ == "__main__":
    print("Building URL map...")
    url_map = build_url_map()
    if not url_map:
        print("No URLs found.")
        sys.exit(1)
    linkify_html(url_map)
    print("Done.")
