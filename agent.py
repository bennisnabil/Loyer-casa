import os,time,json,hashlib,logging,schedule,requests
from bs4 import BeautifulSoup
from datetime import datetime

logging.basicConfig(level=logging.INFO,format="%(asctime)s [%(levelname)s] %(message)s")
log=logging.getLogger("RentWatch")

CONFIG={"budget_min":int(os.getenv("BUDGET_MIN",3000)),"budget_max":int(os.getenv("BUDGET_MAX",6000)),"quartiers":os.getenv("QUARTIERS","maarif,gauthier,hay-riad,anfa,centre-ville,racine").split(","),"telegram_token":os.getenv("TELEGRAM_TOKEN",""),"telegram_chat_id":os.getenv("TELEGRAM_CHAT_ID",""),"scan_interval_min":int(os.getenv("SCAN_INTERVAL",30)),"seen_file":"seen_listings.json"}

HEADERS={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36","Accept-Language":"fr-FR,fr;q=0.9"}

def load_seen():
    if os.path.exists(CONFIG["seen_file"]):
        with open(CONFIG["seen_file"]) as f:return set(json.load(f))
    return set()

def save_seen(seen):
    with open(CONFIG["seen_file"],"w") as f:json.dump(list(seen),f)

def listing_id(url):return hashlib.md5(url.encode()).hexdigest()

def scrape_avito():
    results=[]
    for q in CONFIG["quartiers"]:
        try:
            r=requests.get(f"https://www.avito.ma/fr/casablanca/appartements-%C3%A0_louer?pr={CONFIG['budget_min']},{CONFIG['budget_max']}&q={q}",headers=HEADERS,timeout=15)
            soup=BeautifulSoup(r.text,"html.parser")
            for card in soup.select("article.sc-1nre5ec-1,li[class*='listing']")[:10]:
                try:
                    t=card.select_one("p[itemprop='name'],h2,[class*='title']")
                    p=card.select_one("p[class*='price'],[class*='Price']")
                    l=card.select_one("a[href]")
                    if not(t and p and l):continue
                    price=int("".join(filter(str.isdigit,p.get_text(strip=True).replace("\u202f","").replace(" ","")))or 0)
                    if not(CONFIG["budget_min"]<=price<=CONFIG["budget_max"]):continue
                    href=l["href"]
                    results.append({"source":"Avito.ma","title":t.get_text(strip=True),"price":price,"quartier":q.replace("-"," ").title(),"url":href if href.startswith("http")else f"https://www.avito.ma{href}","found_at":datetime.now().strftime("%d/%m %H:%M")})
                except:continue
        except Exception as e:log.warning(f"Avito {q}: {e}")
    log.info(f"Avito → {len(results)}")
    return results

def scrape_mubawab():
    results=[]
    try:
        r=requests.get(f"https://www.mubawab.ma/fr/sc/casablanca/appartements-a-louer:p:1?minPrice={CONFIG['budget_min']}&maxPrice={CONFIG['budget_max']}",headers=HEADERS,timeout=15)
        soup=BeautifulSoup(r.text,"html.parser")
        for card in soup.select("li.listingBox,div[class*='listing-card']")[:15]:
            try:
                t=card.select_one("h2,h3,[class*='title']")
                p=card.select_one("[class*='price']")
                l=card.select_one("a[href]")
                if not(t and l):continue
                price=int("".join(filter(str.isdigit,(p.get_text(strip=True)if p else"0").replace(" ","")))or 0)
                if price and not(CONFIG["budget_min"]<=price<=CONFIG["budget_max"]):continue
                href=l["href"]
                results.append({"source":"Mubawab.ma","title":t.get_text(strip=True),"price":price,"quartier":"Casablanca","url":href if href.startswith("http")else f"https://www.mubawab.ma{href}","found_at":datetime.now().strftime("%d/%m %H:%M")})
            except:continue
    except Exception as e:log.warning(f"Mubawab: {e}")
    log.info(f"Mubawab → {len(results)}")
    return results

def scrape_sarouty():
    results=[]
    try:
        r=requests.get(f"https://www.sarouty.ma/fr/louer/appartement/casablanca?min_price={CONFIG['budget_min']}&max_price={CONFIG['budget_max']}",headers=HEADERS,timeout=15)
        soup=BeautifulSoup(r.text,"html.parser")
        for card in soup.select("div[class*='property-card'],article[class*='listing']")[:15]:
            try:
                t=card.select_one("h2,h3,[class*='title']")
                p=card.select_one("[class*='price']")
                l=card.select_one("a[href]")
                if not(t and l):continue
                price=int("".join(filter(str.isdigit,(p.get_text(strip=True)if p else"0").replace(" ","")))or 0)
                if price and not(CONFIG["budget_min"]<=price<=CONFIG["budget_max"]):continue
                href=l["href"]
                results.append({"source":"Sarouty.ma","title":t.get_text(strip=True),"price":price,"quartier":"Casablanca","url":href if href.startswith("http")else f"https://www.sarouty.ma{href}","found_at":datetime.now().strftime("%d/%m %H:%M")})
            except:continue
    except Exception as e:log.warning(f"Sarouty: {e}")
    log.info(f"Sarouty → {len(results)}")
    return results

def send_telegram(listing):
    token=CONFIG["telegram_token"];chat_id=CONFIG["telegram_chat_id"]
    if not token or not chat_id:return
    msg=(f"🏠 *Nouvelle annonce — RentWatch Casa*\n\n📍 *{listing['title']}*\n💰 {listing['price']:,} MAD/mois\n📌 {listing['quartier']}\n🕐 {listing['found_at']}\n📡 {listing['source']}\n\n🔗 [Voir l'annonce]({listing['url']})")
    try:
        r=requests.post(f"https://api.telegram.org/bot{token}/sendMessage",json={"chat_id":chat_id,"text":msg,"parse_mode":"Markdown"},timeout=10)
        if r.status_code==200:log.info(f"✅ Telegram → {listing['title']}")
        else:log.warning(f"Telegram {r.status_code}: {r.text}")
    except Exception as e:log.error(f"Telegram: {e}")

def send_telegram_text(text):
    token=CONFIG["telegram_token"];chat_id=CONFIG["telegram_chat_id"]
    if not token or not chat_id:return
    try:requests.post(f"https://api.telegram.org/bot{token}/sendMessage",json={"chat_id":chat_id,"text":text,"parse_mode":"Markdown"},timeout=10)
    except:pass

def run_scan():
    log.info(f"🔍 Scan — {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    seen=load_seen();new=0
    listings=scrape_avito()+scrape_mubawab()+scrape_sarouty()
    for l in listings:
        lid=listing_id(l["url"])
        if lid not in seen:
            send_telegram(l);seen.add(lid);new+=1;time.sleep(2)
    save_seen(seen)
    log.info(f"✅ {new} nouvelle(s) / {len(listings)} trouvées")

if __name__=="__main__":
    send_telegram_text("🚀 *RentWatch Casa activé !*\nJe surveille Avito, Mubawab et Sarouty toutes les 30 min.\nTu recevras ici chaque annonce entre *3 000 et 6 000 MAD*.")
    run_scan()
    schedule.every(CONFIG["scan_interval_min"]).minutes.do(run_scan)
    while True:schedule.run_pending();time.sleep(60)

