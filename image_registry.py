#!/usr/bin/env python3
"""Registro de identidad de imagen de @manzanoshabitat.

Regla permanente de Victor (21-sep-2026): NINGUNA foto se repite en un post ni
en una story durante al menos 360 dias. La identidad es la FOTO fuente, no el
nombre de la tarjeta: `27-azagra-valor.jpg` (post) y `27-azagra-valor-story.jpg`
(story) salen de la MISMA foto, y la misma foto puede estar dos veces en disco
(raw/grande28/salon.jpg y web-fotos/calle-grande-28/gallery__salon-01.jpg).

Estado (gitignorado, local como .daily_state.json):
  .image_index.json      tarjeta -> {photo, phash, src, how}
  .published_images.json historial [{date, kind, card, photo, phash}]

Mismo diseño que ~/palacio-social/image_registry.py ([[palacio-ig-no-repeat-360]]).
"""
import os, json, sys, glob, unicodedata, datetime

LOCAL = os.path.dirname(os.path.abspath(__file__))
INDEX_FILE = os.path.join(LOCAL, ".image_index.json")
LEDGER_FILE = os.path.join(LOCAL, ".published_images.json")

# Fotos fuente (no tarjetas). raw/ recursivo + fotos oficiales de la web por
# proyecto + material real ya publicado.
SRC_GLOBS = [
    os.path.join(LOCAL, "raw", "**", "*.jpg"),
    os.path.join(LOCAL, "raw", "**", "*.jpeg"),
    os.path.join(LOCAL, "raw", "**", "*.png"),
    os.path.join(LOCAL, "web-fotos", "**", "*.jpg"),
    os.path.join(LOCAL, "reales", "published", "*.jpg"),
]
# WHY: los heros de la web existen reescalados a 640/1024/1600; son la MISMA foto
# que hero.jpg y solo meten ruido en el emparejamiento.
SKIP_RE = ("-640.", "-1024.", "-1600.")

# 1 publicacion cada 2 dias = 183/ano x 2 fotos (post + story) = 366 fotos.
NO_REPEAT_DAYS = 360
# Hamming <= 6 sobre aHash 16x16 = misma foto (umbral validado en agolfcars y palacio).
PHASH_NEAR = 6
BITS = 16


def key(card):
    # WHY NFC: macOS devuelve nombres en NFD y CAPTIONS.md en NFC (gotcha de palacio).
    return unicodedata.normalize("NFC", card)


def phash(path, bits=BITS):
    """aHash del cuadrado central de la FOTO fuente. cover() recorta centrado,
    asi que el centro sobrevive tanto al 4:5 del post como al 9:16 de la story."""
    from PIL import Image
    im = Image.open(path).convert("L")
    w, h = im.size
    half = min(w, h) / 2 * 0.88
    im = im.crop((int(w / 2 - half), int(h / 2 - half), int(w / 2 + half), int(h / 2 + half)))
    im = im.resize((bits, bits), Image.LANCZOS)
    px = list(im.getdata()); avg = sum(px) / len(px)
    return "".join("1" if p > avg else "0" for p in px)


def hamming(a, b):
    if a is None or b is None or len(a) != len(b):
        return 9999
    return sum(1 for x, y in zip(a, b) if x != y)


def same_photo(a, b, near=PHASH_NEAR):
    return hamming(a, b) <= near


def load_index():
    try:
        return {key(k): v for k, v in json.load(open(INDEX_FILE, encoding="utf-8")).items()}
    except Exception:
        return {}


def _atomic_dump(obj, path):
    # WHY atomico: el motor puede leer el indice mientras images_tool lo reescribe;
    # un JSON a medias se leeria como indice vacio y todas las tarjetas quedarian
    # "sin identidad" (y el ledger apuntaria filas sin phash, que no bloquean nada).
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=1, ensure_ascii=False)
    os.replace(tmp, path)


def save_index(idx):
    _atomic_dump({key(k): v for k, v in idx.items()}, INDEX_FILE)


def card_phash(card, idx=None):
    idx = idx if idx is not None else load_index()
    e = idx.get(key(card))
    return e.get("phash") if e else None


def load_ledger():
    try:
        return json.load(open(LEDGER_FILE, encoding="utf-8"))
    except Exception:
        return []


def record(date, kind, card, idx=None, ph=None, photo=None):
    """Anota una publicacion JUSTO tras confirmarla (igual que save_state)."""
    idx = idx if idx is not None else load_index()
    e = idx.get(key(card)) or {}
    rows = load_ledger()
    rows.append({"date": str(date), "kind": kind, "card": card,
                 "photo": photo or e.get("photo", "?"), "phash": ph or e.get("phash")})
    _atomic_dump(rows, LEDGER_FILE)
    return rows


def blocked_hashes(today, days=NO_REPEAT_DAYS, rows=None):
    rows = rows if rows is not None else load_ledger()
    if isinstance(today, str):
        today = datetime.date.fromisoformat(today)
    cut = today - datetime.timedelta(days=days)
    out = []
    for r in rows:
        try:
            d = datetime.date.fromisoformat(r["date"])
        except Exception:
            continue
        if d > cut and r.get("phash"):
            out.append((r["phash"], r["date"], r.get("photo", "?"), r.get("card", "?")))
    return out


def is_blocked(ph, blocked, near=PHASH_NEAR):
    """(bloqueada?, motivo). Una tarjeta SIN phash se trata como bloqueada:
    publicar una foto que nadie ha identificado es justo lo que se cierra."""
    if not ph:
        return True, "tarjeta sin identidad en .image_index.json (dala de alta con images_tool.py)"
    for bph, date, photo, card in blocked:
        if hamming(ph, bph) <= near:
            return True, f"misma foto que {card} ({photo}) publicada el {date}"
    return False, ""


def sources():
    out = {}
    for g in SRC_GLOBS:
        for p in sorted(glob.glob(g, recursive=True)):
            if any(s in p for s in SKIP_RE):
                continue
            out.setdefault(os.path.relpath(p, LOCAL), p)
    return out


def build_index(verbose=True):
    """Casa cada tarjeta de posts/ y stories/ con su foto fuente simulando el
    recorte real de cada formato (cover 1080x1350 / 1080x1920) y comparando la
    zona interior (sin marco ni logo)."""
    from PIL import Image

    def cover(im, w, h):
        s = max(w / im.width, h / im.height)
        nw, nh = int(im.width * s + 1), int(im.height * s + 1)
        im = im.resize((nw, nh), Image.LANCZOS)
        return im.crop(((nw - w) // 2, (nh - h) // 2, (nw - w) // 2 + w, (nh - h) // 2 + h))

    def inner(im, bits=BITS):
        im = im.convert("L"); w, h = im.size
        im = im.crop((int(w * .12), int(h * .10), int(w * .88), int(h * .78)))
        im = im.resize((bits, bits), Image.LANCZOS)
        px = list(im.getdata()); avg = sum(px) / len(px)
        return "".join("1" if p > avg else "0" for p in px)

    src = sources()
    sim = {"posts": {}, "stories": {}}; src_ph = {}
    for rel, p in src.items():
        try:
            im = Image.open(p).convert("RGB")
        except Exception:
            continue
        sim["posts"][rel] = inner(cover(im, 1080, 1350))
        sim["stories"][rel] = inner(cover(im, 1080, 1920))
        src_ph[rel] = phash(p)

    old = load_index()
    idx, weak = {}, []
    for sub in ("posts", "stories"):
        for fn in sorted(os.listdir(os.path.join(LOCAL, sub))):
            if not fn.lower().endswith((".jpg", ".jpeg", ".png")):
                continue
            card = key(f"{sub}/{fn}")
            if old.get(card, {}).get("how") in ("add", "manual"):
                idx[card] = old[card]; continue
            s = inner(Image.open(os.path.join(LOCAL, sub, fn)))
            ranked = sorted((hamming(s, ss), rel) for rel, ss in sim[sub].items())
            bd, best = ranked[0] if ranked else (9999, None)
            if best and bd <= 18:
                idx[card] = {"photo": best, "phash": src_ph[best], "src": src[best],
                             "how": f"match(d={bd})"}
            else:
                weak.append((card, best, bd))
    save_index(idx)
    if verbose:
        print(f"indice: {len(idx)} tarjetas · {len(set(v['photo'] for v in idx.values()))} fotos fuente")
        for w in weak:
            print("  ⚠️  sin fuente:", w)
    return idx, weak


if __name__ == "__main__":
    build_index()
