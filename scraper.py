import requests
import json
import datetime
import os
import re
from bs4 import BeautifulSoup

RESULTS_FILE = 'results.json'
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"}

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

def scrape_uk49s_za(draw_type="lunchtime"):
    try:
        url_map = {
            "lunchtime": "https://za.national-lottery.com/uk-49s/results/lunchtime",
            "teatime": "https://za.national-lottery.com/uk-49s/results/teatime",
            "brunchtime": "https://za.national-lottery.com/uk-49s/results/brunchtime",
            "drivetime": "https://za.national-lottery.com/uk-49s/results/drivetime",
        }
        url = url_map.get(draw_type, url_map["lunchtime"])
        r = requests.get(url, headers=HEADERS, timeout=20)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        balls = []
        for el in soup.select('.ball, .result-ball, span.ball, div.ball, li.ball'):
            t = el.get_text(strip=True)
            if re.fullmatch(r'\d{1,2}', t):
                v = int(t)
                if 1 <= v <= 49:
                    balls.append(v)
        if len(balls) >= 7:
            print(f"  [OK-ZA] uk49s-{draw_type}: {balls[:6]} + {balls[6]} from {url}")
            return sorted(balls[:6]), balls[6]
        print(f"  [FAIL-ZA] uk49s-{draw_type}: could not parse {url}")
        return None, None
    except Exception as e:
        print(f"  [ERR-ZA] uk49s-{draw_type}: {e}")
        return None, None

today = datetime.date.today()
date_long = today.strftime("%d %B %Y")
date_iso = today.isoformat()

lotteries = [
    {"slug": "uk49s-lunchtime", "name": "UK49s Lunchtime", "type": "uk49s", "draw": "lunchtime"},
    {"slug": "uk49s-teatime", "name": "UK49s Teatime", "type": "uk49s", "draw": "teatime"},
    {"slug": "uk49s-brunchtime", "name": "UK49s Brunchtime", "type": "uk49s", "draw": "brunchtime"},
    {"slug": "uk49s-drivetime", "name": "UK49s Drivetime", "type": "uk49s", "draw": "drivetime"},
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
    numbers, bonus = None, None
    numbers, bonus = scrape_uk49s(lot["draw"])
    if numbers is None:
        numbers, bonus = scrape_uk49s_za(lot["draw"])
    if numbers is None:
        numbers = prev.get("numbers", [])
        bonus = prev.get("bonus", 0)
        status = "kept-old"
    else:
        status = "updated"
    history = prev.get("history", [])
    if numbers and (not history or history[0].get("date") != date_iso):
        # Only add new entry if date changed - prevents duplicate same-day entries
        entry = {"no": (history[0]["no"]+1) if history else 2482, "date": date_iso, "dateLong": date_long, "numbers": numbers, "bonus": bonus}
        if history and history[0].get("date") == date_iso:
            history[0] = entry  # update same-day result
        else:
            history = [entry] + history[:19]
    elif not history and numbers:
        history = [{"no": 2482, "date": date_iso, "dateLong": date_long, "numbers": numbers, "bonus": bonus}]
    results.append({
        "slug": slug,
        "name": lot["name"],
        "numbers": numbers,
        "bonus": bonus,
        "date": date_iso,
        "dateLong": date_long,
        "history": history,
        "updatedAt": datetime.datetime.utcnow().isoformat() + "Z",
        "live": numbers is not None and status == "updated",
    })
    print(f"  {slug}: {numbers} + {bonus} [{status}]")

# Keep SA data from old file
for slug, prev in old.items():
    if slug not in [l["slug"] for l in lotteries]:
        results.append(prev)

with open(RESULTS_FILE, 'w') as f:
    json.dump(results, f, indent=2)

live_count = sum(1 for r in results if r.get("live"))
print(f"results.json updated - {date_long} - {len(results)} lotteries, {live_count} freshly scraped")
