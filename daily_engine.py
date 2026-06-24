#!/usr/bin/env python3
"""Manzanos Hábitat — DAILY ENGINE para @manzanoshabitat.

Clonado del motor de @palaciodemanzanos / @manzanoswinesusa con:
- Credenciales propias (MANZANOSHABITAT_IG_ACCESS_TOKEN / _ACCOUNT_ID)
- Repo público propio: github.com/victormanzanos/manzanoshabitat-social
- Captions parseadas de CAPTIONS.md (single source of truth)
- Cadencia "1 día sí, 1 día no" en días PARES (ordinal%2==0). Palacio publica
  impares (%2==1), Manzanos Wines %4==0, JMC %4==2 → nunca coinciden el mismo
  día, reparte carga entre cuentas IG y reduce huella anti-bot.
- Idempotencia (1 publicación/día), jitter, defer aleatorio, foto real opcional.

Variables de entorno:
  DRY=1     → preview sin publicar ni email (no necesita credenciales)
  FORCE=1   → salta la guardia de "día de descanso"
"""
import datetime, json, os, random, re, ssl, smtplib, subprocess, time
import urllib.request, urllib.parse, urllib.error
import base64, hashlib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage

# ── CONFIG ────────────────────────────────────────────────────────────────
LOCAL    = os.path.expanduser("~/manzanoshabitat-social")
SECRETS  = os.path.expanduser("~/Code/CyberSecurity/scripts/secrets.sh")
STATE    = os.path.join(LOCAL, ".daily_state.json")
CAPTIONS_FILE = os.path.join(LOCAL, "CAPTIONS.md")
RAW      = "https://raw.githubusercontent.com/victormanzanos/manzanoshabitat-social/main"
BASE     = "https://graph.instagram.com/v23.0"
REPO     = "victormanzanos/manzanoshabitat-social"
H        = "#ManzanosHabitat"   # brand hashtag — siempre se mantiene

# Cadencia: 1 día sí, 1 día no, en días PARES (julian ordinal % 2 == 0)
CYCLE_DIV = 2
CYCLE_DAY = 0

# Foto real intercalada — 1 real cada N posts de marca (drop folder ~/manzanoshabitat-social/reales)
REAL_EVERY = 3
TDIR     = os.path.join(LOCAL, "reales")
DONE_DIR = os.path.join(TDIR, "published")
IMG_EXT  = (".jpg", ".jpeg", ".png")
DEFAULT_REAL_CAPTION = (
    "Una imagen de nuestros proyectos 🏡\n"
    "Construimos hogares en Navarra y La Rioja. Más en el link de la bio.\n\n"
    "#ManzanosHabitat #ObraNueva #Navarra #LaRioja #ViviendaNueva"
)

DRY = os.environ.get("DRY") == "1"

# Credenciales — lazy load para que DRY=1 funcione sin credenciales
TOK = None
IGID = None
def _secret(n):
    return subprocess.check_output([SECRETS, "get", n]).decode().strip()
def ensure_creds():
    global TOK, IGID
    if TOK is None:
        TOK  = _secret("MANZANOSHABITAT_IG_ACCESS_TOKEN")
        IGID = _secret("MANZANOSHABITAT_IG_ACCOUNT_ID")


# ── PARSE CAPTIONS.md → POSTS, STORIES ────────────────────────────────────
def parse_captions(path):
    text = open(path, encoding="utf-8").read()
    sections = re.split(r"^## ", text, flags=re.M)
    posts, stories = [], []
    for sec in sections:
        head = sec.splitlines()[0].strip().upper() if sec.strip() else ""
        if "POSTS" in head and "STOR" not in head:
            target = posts
        elif "STOR" in head:
            target = stories
        else:
            continue
        for entry in re.split(r"^### ", sec, flags=re.M)[1:]:
            lines = entry.splitlines()
            if not lines:
                continue
            m = re.search(r"`([^`]+\.jpg)`", lines[0])
            if not m:
                continue
            filename = m.group(1)
            body = []
            for ln in lines[1:]:
                if ln.startswith("##") or ln.startswith("---"):
                    break
                body.append(ln)
            target.append((filename, "\n".join(body).strip()))
    return posts, stories

POSTS, STORIES = parse_captions(CAPTIONS_FILE)
STORY_FILES = [fn for fn, _ in STORIES]
assert POSTS,   "No se parsearon posts de CAPTIONS.md"
assert STORIES, "No se parsearon stories de CAPTIONS.md"


# ── STATE ─────────────────────────────────────────────────────────────────
def state():
    s = json.load(open(STATE)) if os.path.exists(STATE) else {}
    s.setdefault("post", 0)
    s.setdefault("story", 0)
    s.setdefault("since_real", 0)
    return s
def save_state(s):
    json.dump(s, open(STATE, "w"))


# ── FOTO REAL intercalada (drop folder) ───────────────────────────────────
def real_collect():
    if not os.path.isdir(TDIR):
        return []
    out = []
    for name in sorted(os.listdir(TDIR)):
        path = os.path.join(TDIR, name)
        if not os.path.isfile(path):
            continue
        base, ext = os.path.splitext(name)
        if ext.lower() not in IMG_EXT:
            continue
        cap_file = os.path.join(TDIR, base + ".txt")
        cap = open(cap_file, encoding="utf-8").read().strip() if os.path.exists(cap_file) else DEFAULT_REAL_CAPTION
        out.append((path, cap))
    return out

def gh_upload(local_path, remote_name):
    with open(local_path, "rb") as f:
        content_b64 = base64.b64encode(f.read()).decode()
    remote_path = f"reales/{remote_name}"
    sha = None
    probe = subprocess.run(["gh", "api", f"/repos/{REPO}/contents/{remote_path}"],
                           capture_output=True, text=True)
    if probe.returncode == 0:
        try:    sha = json.loads(probe.stdout).get("sha")
        except: sha = None
    args = ["gh", "api", "--method", "PUT", f"/repos/{REPO}/contents/{remote_path}",
            "-f", f"message=Add real photo {remote_name}", "-f", f"content={content_b64}"]
    if sha: args += ["-f", f"sha={sha}"]
    r = subprocess.run(args, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"gh upload failed: {r.stderr.strip()[:300]}")
    return f"{RAW}/{remote_path}"

def archive_real(path):
    os.makedirs(DONE_DIR, exist_ok=True)
    name = os.path.basename(path)
    os.rename(path, os.path.join(DONE_DIR, name))
    cap_file = os.path.join(TDIR, os.path.splitext(name)[0] + ".txt")
    if os.path.exists(cap_file):
        os.rename(cap_file, os.path.join(DONE_DIR, os.path.basename(cap_file)))


# ── INSTAGRAM GRAPH API ───────────────────────────────────────────────────
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
def api(path, params, method="POST"):
    data = urllib.parse.urlencode(params).encode()
    hdr  = {"User-Agent": UA}
    if method == "GET":
        req = urllib.request.Request(f"{BASE}/{path}?{data.decode()}", headers=hdr)
    else:
        req = urllib.request.Request(f"{BASE}/{path}", data=data, method="POST", headers=hdr)
    try:
        with urllib.request.urlopen(req) as r: return json.load(r)
    except urllib.error.HTTPError as e:
        return {"_http_error": e.code, "body": e.read().decode()}

def wait_ready(cid):
    for _ in range(20):
        st = api(cid, {"fields": "status_code", "access_token": TOK}, "GET").get("status_code")
        if st in ("FINISHED", "ERROR", "EXPIRED"): return st
        time.sleep(4)
    return "TIMEOUT"

def publish_image(url, caption=None, story=False):
    ensure_creds()
    p = {"image_url": url, "access_token": TOK}
    if story:   p["media_type"] = "STORIES"
    if caption: p["caption"]    = caption
    c = api(f"{IGID}/media", p); cid = c.get("id")
    if not cid: return {"error": c}
    if wait_ready(cid) != "FINISHED": return {"error": "container not ready"}
    r = api(f"{IGID}/media_publish", {"creation_id": cid, "access_token": TOK})
    mid = r.get("id")
    if not mid: return {"error": r}
    return api(mid, {"fields": "permalink", "access_token": TOK}, "GET")


# ── EMAIL RESUMEN ─────────────────────────────────────────────────────────
def email_summary(html, post_path, story_path, subject):
    pw = _secret("MANZANOS_SMTP_PASSWORD")
    msg = MIMEMultipart("related")
    msg["Subject"] = subject
    msg["From"]    = "assistant@manzanosenterprises.com"
    msg["To"]      = "victor@manzanos.com"
    msg.attach(MIMEText(html, "html", "utf-8"))
    for cid, path in (("postimg", post_path), ("storyimg", story_path)):
        try:
            with open(path, "rb") as f: img = MIMEImage(f.read())
            img.add_header("Content-ID", f"<{cid}>")
            img.add_header("Content-Disposition", "inline", filename=os.path.basename(path))
            msg.attach(img)
        except Exception as e: print("attach failed", path, e)
    with smtplib.SMTP_SSL("manzanosenterprises-com.correoseguro.dinaserver.com", 465,
                          context=ssl.create_default_context()) as srv:
        srv.login("assistant@manzanosenterprises.com", pw)
        srv.send_message(msg)


# ── CAPTION ROTATION (anti-spam hashtags) ─────────────────────────────────
def rotate_caption(cap):
    body, tags = [], []
    for ln in cap.split("\n"):
        toks = ln.split()
        if toks and all(t.startswith("#") for t in toks):
            tags.extend(toks)
        else:
            body.append(ln)
    if not tags:
        return cap
    brand = [t for t in tags if t.lower() == H.lower()]
    rest  = [t for t in tags if t.lower() != H.lower()]
    random.shuffle(rest)
    k = min(len(rest), random.randint(4, 8))
    chosen = brand + rest[:k]
    random.shuffle(chosen)
    return "\n".join(body).rstrip() + "\n" + " ".join(chosen)


# ── MAIN ──────────────────────────────────────────────────────────────────
def main():
    s = state()
    real_items = real_collect()
    do_real    = bool(real_items) and s.get("since_real", 0) >= REAL_EVERY
    real_path  = real_items[0][0] if real_items else None
    real_cap   = real_items[0][1] if real_items else None

    pf, cap = POSTS[s["post"] % len(POSTS)]
    cap = rotate_caption(cap)
    sf  = STORY_FILES[s["story"] % len(STORY_FILES)]
    post_url  = f"{RAW}/posts/{pf}"
    story_url = f"{RAW}/stories/{sf}"

    if do_real:
        print(f"NEXT = FOTO REAL: {os.path.basename(real_path)}  (since_real={s.get('since_real',0)} ≥ {REAL_EVERY})")
        print(f"--- CAPTION ---\n{real_cap}\n---  (story: {sf})")
    else:
        print(f"NEXT = POST MARCA: {pf}\nSTORY: {sf}\n--- CAPTION ---\n{cap}\n---  (real en {REAL_EVERY - s.get('since_real',0)} posts)")

    if DRY:
        print("DRY RUN — nada publicado.")
        return

    today = str(datetime.date.today())
    if os.environ.get("FORCE") != "1" and datetime.date.today().toordinal() % CYCLE_DIV != CYCLE_DAY:
        print(f"Día de descanso ({today}) — Manzanos Hábitat publica cuando ordinal%{CYCLE_DIV}=={CYCLE_DAY}.")
        return
    if s.get("last_date") == today:
        print(f"Ya se publicó hoy ({today}).")
        return
    if datetime.datetime.now().hour < 14 and random.random() < 0.40:
        print("Aplazo a franja posterior (rompe patrón horario).")
        return
    time.sleep(random.randint(30, 480))  # jitter

    # ── Publicar POST ──────────────────────────────────────────────────────
    is_real = False
    if do_real:
        try:
            h = hashlib.sha1(open(real_path, "rb").read()).hexdigest()[:8]
            base, ext = os.path.splitext(os.path.basename(real_path))
            url = gh_upload(real_path, f"{base}-{h}{ext.lower()}")
            time.sleep(5)
            pr = publish_image(url, caption=real_cap)
            if pr.get("permalink"):
                is_real = True; cap = real_cap; post_url = url
            else:
                print("Foto real falló, fallback a marca:", json.dumps(pr)[:200])
                pr = publish_image(post_url, caption=cap)
        except Exception as e:
            print("EXCEPCIÓN foto real, fallback a marca:", e)
            pr = publish_image(post_url, caption=cap)
    else:
        pr = publish_image(post_url, caption=cap)

    time.sleep(random.randint(20, 120))  # gap humano antes del story
    sr = publish_image(story_url, story=True)

    post_ok  = bool(pr.get("permalink"))
    story_ok = bool(sr.get("permalink") or sr.get("id"))
    if post_ok:
        s["last_date"] = today
        if is_real:
            archive_real(real_path); s["since_real"] = 0
        else:
            s["post"] += 1
            s["since_real"] = s.get("since_real", 0) + 1
    if story_ok:
        s["story"] += 1
    save_state(s)

    plink = pr.get("permalink") or ("ERROR: " + json.dumps(pr)[:220])
    sok   = "publicada ✅" if story_ok else ("ERROR: " + json.dumps(sr)[:220])
    print("post:", plink, "(real)" if is_real else "(marca)")
    print("story:", sok)

    subj = ("📲 Instagram diario — Manzanos Hábitat"
            if post_ok else
            "⚠️ FALLO al publicar — Instagram Manzanos Hábitat (revisar)")
    post_path  = real_path if is_real else os.path.join(LOCAL, "posts", pf)
    story_path = os.path.join(LOCAL, "stories", sf)
    kind = "Foto real (drop folder)" if is_real else f"Post {s['post']}/{len(POSTS)}"
    email_summary(
        f"<p>Publicado hoy en <b>@manzanoshabitat</b> · <b>{kind}</b>:</p>"
        f"<p>📸 <b>Post:</b> <a href='{plink}'>{plink}</a><br>📱 <b>Story:</b> {sok}</p>"
        f"<table cellpadding='6'><tr>"
        f"<td valign='top' align='center'><div style='color:#888;font-size:11px;letter-spacing:1px'>POST</div>"
        f"<img src='cid:postimg' width='300' style='border-radius:10px;border:1px solid #ddd'></td>"
        f"<td valign='top' align='center'><div style='color:#888;font-size:11px;letter-spacing:1px'>STORY</div>"
        f"<img src='cid:storyimg' width='210' style='border-radius:10px;border:1px solid #ddd'></td>"
        f"</tr></table>"
        f"<p style='color:#888;font-size:12px'>Caption:</p>"
        f"<pre style='white-space:pre-wrap;color:#555;font-size:12px'>{cap}</pre>"
        f"<p style='color:#aaa;font-size:11px'>Cadencia 1-sí-1-no (días pares) · rotación automática.</p>",
        post_path, story_path, subject=subj
    )


if __name__ == "__main__":
    main()
