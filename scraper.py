import requests
import json
import datetime
import os
import re
from bs4 import BeautifulSoup

RESULTS_FILE = 'results.json'
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

def extract_balls_from_section(soup, keyword, count=7, max_num=49):
    for txt in soup.find_all(string=re.compile(keyword, re.I)):
        parent = txt.parent
        node = parent
        for _ in range(4):
            if node is None:
                break
            balls = []
            for el in node.find_all(['span', 'div', 'li', 'p', 'b']):
                t = el.get_text(strip=True)
                if re.fullmatch(r'\d{1,2}', t):
                    v = int(t)
                    if 1 <= v <= max_num:
                        balls.append(v)
            seen, uniq = set(), []
            for b in balls:
                if b not in seen:
                    seen.add(b)
                    uniq.append(b)
            if len(uniq) >= count:
                return sorted(uniq[:count-1]), uniq[count-1]
            node = node.parent
    return None, None

def scrape_uk49s(draw_type="teatime"):
    try:
        url = "https://www.49s.co.uk/49s-results"
        r = requests.get(url, headers=HEADERS, timeout=20)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        nums, bonus = extract_balls_from_section(soup, draw_type, count=7, max_num=49)
        if nums and bonus:
            print(f"  [OK] uk49s-{draw_type}: {nums} + {bonus}")
            return nums, bonus
        balls = []
        for el in soup.select('.ball, .result-ball, .lotto-ball'):
            t = el.get_text(strip=True)
            if re.fullmatch(r'\d{1,2}', t) and 1 <= int(t) <= 49:
                balls.append(int(t))
        if len(balls) >= 7:
            print(f"  [OK-fallback] uk49s-{draw_type}: {balls[:6]} + {balls[6]}")
            return sorted(balls[:6]), balls[6]
        print(f"  [FAIL] uk49s-{draw_type}: could not parse")
        return None, None
    except Exception as e:
        print(f"  [ERR] uk49s-{draw_type}: {e}")
        return None, None

today = datetime.date.today()
date_long = today.strftime("%d %B %Y")
date_iso = today.isoformat()

lotteries = [
    {"slug": "uk49s-lunchtime", "name": "UK49s Lunchtime", "draw": "lunchtime"},
    {"slug": "uk49s-teatime", "name": "UK49s Teatime", "draw": "teatime"},
    {"slug": "uk49s-brunchtime", "name": "UK49s Brunchtime", "draw": "brunchtime"},
    {"slug": "uk49s-drivetime", "name": "UK49s Drivetime", "draw": "drivetime"},
]

old = {}
if os.path.exists(RESULTS_FILE):
    try:
        with open(RESULTS_FILE) as f:
            for item in json.load(f):
                old[item["slug"]] = item
    except Exception as e:
        print(f"Could not read old {RESULTS_FILE}: {e}")

results = []
for lot in lotteries:
    slug = lot["slug"]
    prev = old.get(slug, {})
    numbers, bonus = scrape_uk49s(lot["draw"])
    if numbers is None:
        numbers = prev.get("numbers", [7,14,22,31,38,45])
        bonus = prev.get("bonus", 9)
        status = "kept-old"
    else:
        status = "updated"
    history = prev.get("history", [])
    if numbers and (not history or history[0].get("numbers") != numbers or history[0].get("date") != date_iso):
        entry = {"no": 2481 - len(history), "date": date_iso, "dateLong": date_long, "numbers": numbers, "bonus": bonus}
        history = [entry] + history[:19]
    elif not history and numbers:
        history = [{"no": 2481, "date": date_iso, "dateLong": date_long, "numbers": numbers, "bonus": bonus}]
    results.append({
        "slug": slug,
        "name": lot["name"],
        "numbers": numbers,
        "bonus": bonus,
        "date": date_iso,
        "dateLong": date_long,
        "history": history,
        "updatedAt": datetime.datetime.utcnow().isoformat() + "Z",
        "live": status == "updated",
    })
    print(f"  {slug}: {numbers} + {bonus} [{status}]")

with open(RESULTS_FILE, 'w') as f:
    json.dump(results, f, indent=2)

print(f"results.json updated - {date_long} - {len(results)} lotteries")
