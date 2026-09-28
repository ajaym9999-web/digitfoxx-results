import requests
from bs4 import BeautifulSoup
import json
import os
import re
from datetime import datetime

# ================= CONFIG - SAME AS WORKING uk49_bot.py =================
SOURCE_URL = "https://za.national-lottery.com/results"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
}

CORE_GAMES = {
    "UK49s Lunchtime": {"aliases": ["uk49s lunchtime", "uk 49s lunchtime", "lunchtime"], "slug": "uk49s-lunchtime"},
    "UK49s Teatime": {"aliases": ["uk49s teatime", "uk 49s teatime", "teatime"], "slug": "uk49s-teatime"},
    "UK49s Brunchtime": {"aliases": ["uk49s brunchtime", "uk 49s brunchtime", "brunchtime"], "slug": "uk49s-brunchtime"},
    "UK49s Drivetime": {"aliases": ["uk49s drivetime", "uk 49s drivetime", "drivetime"], "slug": "uk49s-drivetime"},
}

RESULTS_FILE = "results.json"

def load_existing():
    if os.path.exists(RESULTS_FILE):
        try:
            with open(RESULTS_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return []

def fetch_from_za_national_lottery():
    print(f"🔍 Scraping from {SOURCE_URL} (WORKING METHOD from uk49_bot.py)...")
    draw_results = {}
    try:
        res = requests.get(SOURCE_URL, headers=HEADERS, timeout=20)
        print(f"  Status: {res.status_code}")
        if res.status_code != 200:
            return draw_results

        soup = BeautifulSoup(res.text, "html.parser")

        for h in soup.find_all(["h2", "h3", "h4"]):
            raw_title = h.get_text().strip().lower()
            if not raw_title:
                continue

            matched_key = None
            for key, conf in CORE_GAMES.items():
                for alias in conf["aliases"]:
                    if alias == raw_title:
                        matched_key = key
                        break
                if matched_key:
                    break

            if not matched_key:
                continue

            print(f"  Found section: {matched_key}")

            parent = h.find_parent("div")
            while parent and len(parent.select(".ball, .draw-ball, .result-ball, ul.numbers li, .balls span")) == 0:
                parent = parent.find_parent("div")
                if not parent or parent.name == "body":
                    break

            if not parent:
                continue

            ball_elements = parent.select(".ball, .draw-ball, .result-ball, ul.numbers li, .balls span")
            balls = []
            for b in ball_elements:
                val = b.get_text().strip()
                if val.isdigit():
                    num = int(val)
                    if 1 <= num <= 49:
                        balls.append(num)

            date_match = re.search(
                r"(\b\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4})",
                parent.get_text(),
                re.IGNORECASE
            )
            draw_date = datetime.now().strftime("%Y-%m-%d")
            if date_match:
                try:
                    # Try multiple date formats
                    for fmt in ["%d %B %Y", "%d %b %Y"]:
                        try:
                            dt = datetime.strptime(date_match.group(1).strip(), fmt)
                            draw_date = dt.strftime("%Y-%m-%d")
                            break
                        except:
                            pass
                except:
                    pass

            if balls and len(balls) >= 7:
                main_balls = balls[:-1][:6]
                booster = balls[-1]
                draw_results[matched_key] = {
                    "date": draw_date,
                    "numbers": main_balls,
                    "bonus": booster
                }
                print(f"    ✅ {matched_key}: {main_balls} + {booster} ({draw_date})")
            elif balls and len(balls) >= 6:
                main_balls = balls[:6]
                booster = balls[6] if len(balls) > 6 else balls[-1]
                draw_results[matched_key] = {
                    "date": draw_date,
                    "numbers": main_balls,
                    "bonus": booster
                }
                print(f"    ✅ {matched_key}: {main_balls} + {booster} ({draw_date})")

    except Exception as e:
        print(f"❌ Scraper error: {e}")
        import traceback
        traceback.print_exc()

    return draw_results

def fetch_fallback_uk49sresults():
    """Fallback - same as before"""
    print("\n🔍 FALLBACK: uk49sresults.co.uk...")
    # Keep simple for fallback
    return {}

def main():
    existing = load_existing()
    existing_map = {x['slug']: x for x in existing}
    
    fetched = fetch_from_za_national_lottery()
    
    if not fetched or len(fetched) < 2:
        print("⚠️ Not enough from primary, trying fallback...")
        fb = fetch_fallback_uk49sresults()
        for k,v in fb.items():
            if k not in fetched:
                fetched[k] = v

    if not fetched:
        print("❌ Both failed, keeping old file")
        return

    print(f"\n📊 Fetched {len(fetched)} draws from za.national-lottery.com")

    new_data = []
    for game_name, conf in CORE_GAMES.items():
        slug = conf['slug']
        if game_name in fetched:
            f = fetched[game_name]
            old = existing_map.get(slug, {})
            history = old.get('history', [])
            
            # If new date, add to history
            if not history or history[0]['date'] != f['date']:
                print(f"  Adding new history for {slug}: {f['date']}")
                new_entry = {
                    "no": (history[0]['no'] + 1) if history and 'no' in history[0] else 2485,
                    "date": f['date'],
                    "dateLong": datetime.strptime(f['date'], "%Y-%m-%d").strftime("%d %B %Y"),
                    "numbers": f['numbers'],
                    "bonus": f['bonus']
                }
                history = [new_entry] + history
                history = history[:30]
            else:
                print(f"  {slug} already has {f['date']}")
            
            new_item = {
                "slug": slug,
                "name": game_name,
                "numbers": f['numbers'],
                "bonus": f['bonus'],
                "date": f['date'],
                "dateLong": datetime.strptime(f['date'], "%Y-%m-%d").strftime("%d %B %Y"),
                "history": history,
                "updatedAt": datetime.utcnow().isoformat() + "Z",
                "live": True
            }
            new_data.append(new_item)
        else:
            if slug in existing_map:
                new_data.append(existing_map[slug])
                print(f"  {slug} not fetched, keeping old {existing_map[slug]['date']}")

    # Keep SA games as is (don't delete)
    for item in existing:
        if item['slug'].startswith('sa-'):
            new_data.append(item)

    with open(RESULTS_FILE, 'w') as f:
        json.dump(new_data, f, indent=2)
    
    print(f"\n✅ SAVED {RESULTS_FILE} with {len(new_data)} items")
    print("🎯 DONE - This uses SAME logic as working uk49_bot.py!")

if __name__ == "__main__":
    main()
