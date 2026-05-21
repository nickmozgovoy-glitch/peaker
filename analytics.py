#!/usr/bin/env python3
"""Peak Analytics — extracts stats from peak.db for documentation."""

import sqlite3
from datetime import datetime
from collections import Counter

DB_NAME = "peak.db"

def analyze():
    conn = sqlite3.connect(DB_NAME)
    
    # Total events
    total = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    if total == 0:
        print("No events in database yet.")
        return
    
    # Date range
    first_ts = conn.execute("SELECT MIN(ts) FROM events").fetchone()[0]
    last_ts = conn.execute("SELECT MAX(ts) FROM events").fetchone()[0]
    
    # Events per day
    events_by_day = conn.execute("""
        SELECT DATE(ts) as day, COUNT(*) as count, 
               AVG(score) as avg_score, MAX(score) as max_score
        FROM events 
        GROUP BY day 
        ORDER BY day
    """).fetchall()
    
    # Top 10 events by score
    top_events = conn.execute("""
        SELECT canonical, score, sources, ts 
        FROM events 
        ORDER BY score DESC 
        LIMIT 10
    """).fetchall()
    
    # Source popularity
    all_sources = []
    for row in conn.execute("SELECT sources FROM events"):
        for src in row[0].split(", "):
            all_sources.append(src)
    source_counts = Counter(all_sources)
    
    conn.close()
    
    # Print report
    print("=" * 55)
    print("  PEAK DETECTOR — ANALYTICS REPORT")
    print("=" * 55)
    print(f"  Period: {first_ts[:10]} to {last_ts[:10]}")
    print(f"  Total events detected: {total}")
    print()
    
    print("  BY DAY:")
    for day, count, avg_score, max_score in events_by_day:
        print(f"    {day}: {count} events, avg score {avg_score:.1f}, max {max_score}")
    print()
    
    print("  TOP 10 EVENTS:")
    for i, (canonical, score, sources, ts) in enumerate(top_events, 1):
        print(f"    {i}. [{score}] {canonical[:70]}...")
        print(f"       Sources: {sources}")
    print()
    
    print("  SOURCE FREQUENCY:")
    for src, count in source_counts.most_common():
        print(f"    {src}: {count} appearances")
    print()
    
    # Save to file
    with open("analytics_report.txt", "w") as f:
        f.write(f"Peak Detector Analytics Report\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write(f"Period: {first_ts[:10]} to {last_ts[:10]}\n")
        f.write(f"Total events: {total}\n\n")
        f.write("BY DAY:\n")
        for day, count, avg_score, max_score in events_by_day:
            f.write(f"  {day}: {count} events, avg score {avg_score:.1f}, max {max_score}\n")
        f.write("\nTOP 10 EVENTS:\n")
        for i, (canonical, score, sources, ts) in enumerate(top_events, 1):
            f.write(f"  {i}. [{score}] {canonical[:100]}\n     Sources: {sources}\n")
        f.write("\nSOURCE FREQUENCY:\n")
        for src, count in source_counts.most_common():
            f.write(f"  {src}: {count}\n")
    
    print("  Report saved to analytics_report.txt")

if __name__ == "__main__":
    analyze()
