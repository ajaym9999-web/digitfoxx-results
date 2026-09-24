import requests
import json
import datetime
import os
import re
from bs4 import BeautifulSoup

RESULTS_FILE = 'results.json'
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"}

def extract_balls_from_section(soup, keyword, count=7, max_num=49):
    """Find a heading containing keyword, then collect number-like balls near it."""
    for txt in soup.find_all(string=re.compile(keyword, re.I)):
        parent = txt.parent
        node = parent
        for _ in range(4):
            if node is None:
                break
            balls = []
            for el in node.find_all(['span', 'div', 'li', 'p', 'b']):
                t = el.get_text(strip=True)
                if re.fullmatch(r'\\d{1,2}', t):
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
    """Scrape real UK49s numbers from 49s.co.uk. Returns (numbers[6], bonus) or (None, None)."""
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
            if re.fullmatch(r'\\d{1,2}', t) and 1 <= int(t) <= 49:
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
    """Fallback: scrape from za.national-lottery.com/uk-49s/results/lunchtime"""
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
        # The balls are in div with class ball or similar, look for numbers in circles
        balls = []
        for el in soup.select('.ball, .result-ball, span.ball, div.ball, li.ball'):
            t = el.get_text(strip=True)
            if re.fullmatch(r'\d{1,2}', t):
                v = int(t)
                if 1 <= v <= 49:
                    balls.append(v)
        # Also parse from text containing numbers
        if len(balls) < 7:
            # Try to find the main result area - look for numbers in the page
            text = soup.get_text()
            # Find patterns like 14 21 25 26 46 47 49 near each other
            m = re.findall(r'\b([1-4]?\d)\b', text)
            # filter to reasonable
            candidates = [int(x) for x in m if 1 <= int(x) <= 49]
            # Take first 7 unique in order if more
            if len(candidates) >= 7:
                seen=set()
                uniq=[]
                for n in candidates:
                    if n not in seen:
                        seen.add(n)
                        uniq.append(n)
                    if len(uniq)>=7:
                        break
                balls = uniq
        if len(balls) >= 7:
            print(f"  [OK-ZA] uk49s-{draw_type}: {balls[:6]} + {balls[6]} from {url}")
            return sorted(balls[:6]), balls[6]
        print(f"  [FAIL-ZA] uk49s-{draw_type}: could not parse {url}")
        return None, None
    except Exception as e:
        print(f"  [ERR-ZA] uk49s-{draw_type}: {e}")
        return None, None


def scrape_sa(game):
    """Scrape SA lottery numbers from nationallottery.co.za. Returns (numbers, bonus) or (None, None)."""
    urls = [
        "https://www.nationallottery.co.za/index.php?task=results",
        "https://www.nationallottery.co.za/",
    ]
    game_map = {
        "daily": ("daily lotto", 5, 36),
        "lotto": ("lotto", 6, 52),
        "plus1": ("lotto plus 1", 6, 52),
        "plus2": ("lotto plus 2", 6, 52),
        "powerball": ("powerball", 5, 50),
        "powerball-plus": ("powerball plus", 5, 50),
        "pick3": ("pick 3", 3, 10),
    }
    keyword, count, max_num = game_map.get(game, ("lotto", 6, 52))
    for url in urls:
        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")
            nums, bonus = extract_balls_from_section(soup, keyword, count=count + 1, max_num=max_num)
            if nums:
                print(f"  [OK] sa-{game}: {nums} + {bonus}")
                return nums, bonus if bonus else 0
        except Exception as e:
            print(f"  [ERR] sa-{game} @ {url}: {e}")
            continue
    print(f"  [FAIL] sa-{game}: could not parse, keeping old data")
    return None, None

today = datetime.date.today()
date_long = today.strftime("%d %B %Y")
date_iso = today.isoformat()

lotteries = [
    {"slug": "uk49s-lunchtime", "name": "UK49s Lunchtime", "type": "uk49s", "draw": "lunchtime"},
    {"slug": "uk49s-teatime", "name": "UK49s Teatime", "type": "uk49s", "draw": "teatime"},
    {"slug": "uk49s-brunchtime", "name": "UK49s Brunchtime", "type": "uk49s", "draw": "brunchtime"},
    {"slug": "uk49s-drivetime", "name": "UK49s Drivetime", "type": "uk49s", "draw": "drivetime"},
    {"slug": "sa-daily-lotto", "name": "SA Daily Lotto", "type": "sa", "game": "daily"},
    {"slug": "sa-lotto", "name": "SA Lotto", "type": "sa", "game": "lotto"},
    {"slug": "sa-lotto-plus-1", "name": "SA Lotto Plus 1", "type": "sa", "game": "plus1"},
    {"slug": "sa-lotto-plus-2", "name": "SA Lotto Plus 2", "type": "sa", "game": "plus2"},
    {"slug": "sa-powerball", "name": "SA PowerBall", "type": "sa", "game": "powerball"},
    {"slug": "sa-powerball-plus", "name": "SA PowerBall Plus", "type": "sa", "game": "powerball-plus"},
    {"slug": "sa-pick-3", "name": "SA Pick 3", "type": "sa", "game": "pick3"},
    {"slug": "uk-6-49", "name": "UK 6/49", "type": "static"},
    {"slug": "france-loto", "name": "France Loto", "type": "static"},
    {"slug": "eurojackpot", "name": "EuroJackpot", "type": "static"},
    {"slug": "gosloto-6-45", "name": "Gosloto 6/45", "type": "static"},
    {"slug": "gosloto-4-20", "name": "Gosloto 4/20", "type": "static"},
    {"slug": "gosloto-5-36", "name": "Gosloto 5/36", "type": "static"},
    {"slug": "sa-lotto-5-max", "name": "SA Lotto 5 Max", "type": "static"},
    {"slug": "sa-sportstake-13", "name": "SA SportStake 13", "type": "static"},
    {"slug": "sa-sportstake-8", "name": "SA SportStake 8", "type": "static"},
    {"slug": "sa-daily-lotto-midday", "name": "SA Daily Lotto Midday", "type": "static"},
    {"slug": "sa-raffle", "name": "SA Raffle", "type": "static"},
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
    if lot["type"] == "uk49s":
        numbers, bonus = scrape_uk49s(lot["draw"])
        if numbers is None:
            numbers, bonus = scrape_uk49s_za(lot["draw"])
    elif lot["type"] == "sa":
        numbers, bonus = scrape_sa(lot["game"])
    if numbers is None:
        numbers = prev.get("numbers", [])
        bonus = prev.get("bonus", 0)
        status = "kept-old"
    else:
        status = "updated"
    history = prev.get("history", [])
    if numbers and (not history or history[0].get("numbers") != numbers or history[0].get("date") != date_iso):
        entry = {"no": 2481 - len(history), "date": date_iso, "dateLong": date_long,
                 "numbers": numbers, "bonus": bonus}
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
        "live": numbers is not None and status == "updated",
    })
    print(f"  {slug}: {numbers} + {bonus} [{status}]")

with open(RESULTS_FILE, 'w') as f:
    json.dump(results, f, indent=2)

live_count = sum(1 for r in results if r.get("live"))
print(f"results.json updated - {date_long} - {len(results)} lotteries, {live_count} freshly scraped")
