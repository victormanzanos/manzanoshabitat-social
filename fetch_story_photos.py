#!/usr/bin/env python3
"""Trae fotos VERTICALES de Pexels para STORIES de ambiente de @manzanoshabitat.

Regla de 360 dias (Victor, 21-sep-2026): hacen falta 366 fotos distintas al ano.
Pexels es gratis (PEXELS_API_KEY en Keychain) y NO gasta la cuota de SerpAPI que
comparten el blog writer, siglo-daily-pulse y mobility ([[serpapi-quota]]).

Solo AMBIENTE (paisaje, vida en familia, vendimia, mercado, mudanza). NUNCA
viviendas ni interiores: con el sello MH se leerian como nuestras (Art. I,
[[palacio-ig-identidad-imagen]]). Todo lo que baja se revisa A OJO en hoja de
contacto antes de darlo de alta con images_tool.py.

    /usr/bin/python3 fetch_story_photos.py [por_query=8]
Deja las fotos en raw/pexels-story/ y un manifiesto pexels_story.json.
⚠️ Pexels responde 403 al UA de urllib y a las rafagas: UA de navegador + 1,6 s.
"""
import os, sys, json, time, hashlib, subprocess, urllib.request, urllib.parse, io
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import image_registry as REG
from PIL import Image

LOCAL = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(LOCAL, "raw", "pexels-story")
MAN = os.path.join(LOCAL, "pexels_story.json")
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
PAUSE = 1.6   # WHY: Pexels corta rafagas con 403/429 (visto en palacio y wines)
MAXPX = 2400  # suficiente para 1080x1920 tras cover(); los originales de 6000 px sobran

QUERIES = [
    "vineyard rows autumn", "grape harvest hands", "vineyard sunset aerial", "wine grapes close up",
    "family walking countryside", "grandparents grandchildren park", "children playing in park",
    "couple holding house keys", "moving boxes new home", "family picnic field",
    "dog running grass", "friends dinner terrace summer", "farmers market vegetables",
    "fresh bread bakery", "olive tree field", "wheat field sunset", "poppy field spain",
    "almond blossom", "river reeds sunset", "sunflower field", "cyclist country road",
    "morning coffee balcony", "tapas table", "red wine glasses toast", "autumn leaves path",
    "snowy mountains pyrenees", "hiking trail mountains spain", "stone village street",
    "old town cobblestone street spain", "church bell tower village", "rural landscape spain",
    "desert badlands spain", "hot air balloon sunrise", "starry sky countryside",
    "family garden barbecue", "kids bicycle street", "woman reading book garden",
    "architect blueprint plans", "construction crane sunset", "hands with key",
]

def key():
    return subprocess.check_output([os.path.expanduser("~/Code/CyberSecurity/scripts/secrets.sh"),
                                    "get", "PEXELS_API_KEY"], text=True).strip()

def get(url, k, raw=False):
    req = urllib.request.Request(url, headers={"Authorization": k, "User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read() if raw else json.load(r)

def main(per_q=8):
    os.makedirs(OUT, exist_ok=True)
    k = key()
    man = json.load(open(MAN)) if os.path.exists(MAN) else {}
    known = [v["phash"] for v in REG.load_index().values() if v.get("phash")]
    known += [v["phash"] for v in man.values()]
    md5s = {v["md5"] for v in man.values()}
    for q in QUERIES:
        try:
            d = get("https://api.pexels.com/v1/search?" + urllib.parse.urlencode(
                {"query": q, "per_page": 20, "orientation": "portrait", "size": "large"}), k)
        except Exception as e:
            print("⚠️ busqueda", q, e); time.sleep(PAUSE * 3); continue
        got = 0
        for ph in d.get("photos", []):
            if got >= per_q:
                break
            pid = str(ph["id"])
            if any(v["id"] == pid for v in man.values()):
                continue
            time.sleep(PAUSE)
            try:
                # WHY original redimensionado por el CDN: el original pesa 10-25 MB (8 fotos en
                # 10 min) y large2x se queda en 867x1300 en vertical (no cubre una story 1080x1920).
                b = get(ph["src"]["original"] + "?auto=compress&cs=tinysrgb&h=2400", k, raw=True)
                im = Image.open(io.BytesIO(b)).convert("RGB")
            except Exception as e:
                print("  ⚠️ descarga", pid, e); continue
            if min(im.size) < 1080:
                print("  · baja resolucion", pid, im.size, flush=True); continue
            md5 = hashlib.md5(b).hexdigest()
            im.thumbnail((MAXPX, MAXPX))
            slug = "px-" + "-".join(q.split()[:2]) + f"-{pid}"
            path = os.path.join(OUT, slug + ".jpg")
            im.save(path, "JPEG", quality=90)
            p = REG.phash(path)
            if md5 in md5s or any(REG.same_photo(p, x) for x in known):
                os.remove(path); continue
            man[slug] = {"id": pid, "md5": md5, "phash": p, "query": q, "alt": ph.get("alt", ""),
                         "author": ph.get("photographer", ""), "url": ph.get("url", "")}
            known.append(p); md5s.add(md5); got += 1
            json.dump(man, open(MAN, "w"), indent=1, ensure_ascii=False)
        print(f"{q:40s} +{got}  (total {len(man)})", flush=True)
        time.sleep(PAUSE)

if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 8)
