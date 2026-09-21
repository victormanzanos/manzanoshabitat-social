#!/usr/bin/env python3
"""
Manzanos Hábitat — Pexels → tarjeta de marca (post + story).

Busca una foto VERTICAL de alta resolución en Pexels, la descarga a raw/pexels/
y la pasa por el pipeline de marca (make_manzanoshabitat.py: marco doble dorado,
acentos de esquina, logo MH abajo), dejando el POST 1080x1350 y la STORY 1080x1920
listos para la rotación del feed.

La clave de la API NUNCA se guarda en el código: se lee del Keychain
(Constitución Art. III) vía CyberSecurity/scripts/secrets.sh get PEXELS_API_KEY.

⚠️ USO CON PROVENIENCIA (Constitución Art. I): estas fotos son ATMÓSFERA / ESTILO
DE VIDA (paisaje de La Rioja/Navarra, texturas, materiales, lifestyle), NO renders
de una vivienda concreta. NUNCA presentes una foto de stock como si fuera una
unidad real de un proyecto (G28, Azagra, Villafranca…): eso engañaría al lead.
Para las unidades reales se usan los renders del proyecto (raw/<proyecto>/...).

Uso:
    # Descarga + genera post y story de marca a partir del mejor resultado:
    python3 fetch_pexels.py "la rioja vineyard sunset" atmosfera-rioja

    # Elegir otro resultado de la lista (0 = primero, por defecto):
    python3 fetch_pexels.py "luxury marble interior detail" detalle-marmol --pick 2

    # Solo post o solo story:
    python3 fetch_pexels.py "autumn vineyard" otono --post-only
    python3 fetch_pexels.py "cozy modern living room" salon --story-only

    # Ver los 10 mejores resultados sin descargar (para elegir --pick):
    python3 fetch_pexels.py "la rioja landscape" _ --list
"""
import os, sys, json, subprocess, urllib.request, urllib.parse, argparse

LOCAL   = os.path.expanduser("~/manzanoshabitat-social")
RAW_DIR = os.path.join(LOCAL, "raw", "pexels")
SECRETS = os.path.expanduser("~/Code/CyberSecurity/scripts/secrets.sh")

# Portrait para stories/posts verticales; large2x = suficiente resolución para
# cubrir 1080x1920 sin pixelar tras el crop `cover()`.
PER_PAGE = 15          # margen para elegir con --pick sin gastar cuota de más
ORIENT   = "portrait"  # el feed de MH es vertical (post 4:5 y story 9:16)
UA = "MHBlogBot/1.0 (https://www.manzanoshabitat.com; mh@manzanos.com)"


def get_key():
    try:
        k = subprocess.check_output([SECRETS, "get", "PEXELS_API_KEY"], text=True).strip()
    except Exception as e:
        sys.exit(f"No se pudo leer PEXELS_API_KEY del Keychain: {e}")
    if not k:
        sys.exit("PEXELS_API_KEY vacía en el Keychain.")
    return k


def search(query, key):
    qs = urllib.parse.urlencode({
        "query": query, "per_page": PER_PAGE, "orientation": ORIENT, "size": "large",
    })
    req = urllib.request.Request(
        f"https://api.pexels.com/v1/search?{qs}",
        headers={"Authorization": key, "User-Agent": UA},
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.load(r)
    photos = data.get("photos", [])
    if not photos:
        sys.exit(f"Sin resultados en Pexels para: {query!r}")
    return photos


def download(photo, slug, key):
    os.makedirs(RAW_DIR, exist_ok=True)
    # Mejor calidad disponible sin ser gigante: original o large2x.
    src = photo["src"].get("original") or photo["src"]["large2x"]
    out = os.path.join(RAW_DIR, f"{slug}.jpg")
    req = urllib.request.Request(src, headers={"Authorization": key, "User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r, open(out, "wb") as f:
        f.write(r.read())
    # Verifica que sea imagen real (no una página de error), como el gotcha de Wikimedia.
    ft = subprocess.check_output(["file", "-b", out], text=True).lower()
    if "image" not in ft:
        os.remove(out)
        sys.exit(f"La descarga NO es imagen (file: {ft.strip()}). Abortado.")
    return out


def brand(src_rel, slug, kind):
    """Llama a make_manzanoshabitat.py post|story sobre raw/<src_rel>."""
    out_name = f"{slug}.jpg" if kind == "post" else f"{slug}-story.jpg"
    subprocess.check_call([
        sys.executable, os.path.join(LOCAL, "make_manzanoshabitat.py"),
        kind, src_rel, out_name,
    ])
    sub = "posts" if kind == "post" else "stories"
    return os.path.join(LOCAL, sub, out_name)


def main():
    ap = argparse.ArgumentParser(description="Pexels → tarjeta de marca MH")
    ap.add_argument("query")
    ap.add_argument("slug", help="nombre base del archivo de salida (kebab-case)")
    ap.add_argument("--pick", type=int, default=0, help="índice del resultado (0=primero)")
    ap.add_argument("--list", action="store_true", help="lista resultados y sale")
    ap.add_argument("--post-only", action="store_true")
    ap.add_argument("--story-only", action="store_true")
    args = ap.parse_args()

    key = get_key()
    photos = search(args.query, key)

    if args.list:
        for i, p in enumerate(photos):
            print(f"[{i}] {p['width']}x{p['height']}  por {p['photographer']}  {p['url']}")
        return

    if args.pick >= len(photos):
        sys.exit(f"--pick {args.pick} fuera de rango (hay {len(photos)} resultados).")
    photo = photos[args.pick]

    src = download(photo, args.slug, key)
    src_rel = os.path.relpath(src, os.path.join(LOCAL, "raw"))
    print(f"Descargada: {src}  ({photo['width']}x{photo['height']})")
    print(f"Crédito Pexels: {photo['photographer']} — {photo['url']}")

    outs = []
    if not args.story_only:
        outs.append(brand(src_rel, args.slug, "post"))
    if not args.post_only:
        outs.append(brand(src_rel, args.slug, "story"))

    print("\n✓ Tarjetas de marca generadas:")
    for o in outs:
        print(f"   {o}")
    print("\nSiguiente paso: revisa las imágenes, añade sus captions a CAPTIONS.md")
    print("(sección POSTS/STORIES) y haz git add+push del repo para que la Graph")
    print("API pueda leer las raw URLs.")


if __name__ == "__main__":
    main()
