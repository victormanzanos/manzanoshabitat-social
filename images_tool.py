#!/usr/bin/env python3
"""Herramienta de imagenes de @manzanoshabitat (regla de 360 dias, Victor 21-sep-2026).

    /usr/bin/python3 images_tool.py check          auditoria de baraja e historial
    /usr/bin/python3 images_tool.py plan [N]       simula las proximas N publicaciones
    /usr/bin/python3 images_tool.py add post|story <foto-fuente> <tarjeta.jpg>
    /usr/bin/python3 images_tool.py reindex        reconstruye .image_index.json

`add` es la UNICA via de alta: rechaza (exit 2) cualquier foto ya presente en la
baraja por md5 o hash perceptual. Llamar a make_manzanoshabitat.py directamente
se salta el dedup. ⚠️ Usa SIEMPRE /usr/bin/python3 (el interprete de launchd).
"""
import os, sys, json, hashlib, datetime, importlib.util

LOCAL = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, LOCAL)
import image_registry as REG  # noqa: E402

NEED = 366  # 183 publicaciones/ano (1 de cada 2 dias) x 2 fotos (post + story)


def engine():
    os.environ["DRY"] = "1"
    spec = importlib.util.spec_from_file_location("de", os.path.join(LOCAL, "daily_engine.py"))
    m = importlib.util.module_from_spec(spec); sys.modules["de"] = m
    spec.loader.exec_module(m)
    return m


def clusters(phashes):
    reps = []
    for ph in phashes:
        if ph and not any(REG.same_photo(ph, r) for r in reps):
            reps.append(ph)
    return reps


def cmd_check():
    m = engine(); idx = REG.load_index(); led = REG.load_ledger()
    pcards = [f"posts/{f}" for f, _ in m.POSTS]
    scards = [f"stories/{f}" for f in m.STORY_FILES]
    noid = [c for c in pcards + scards if not REG.card_phash(c, idx)]
    allf = clusters(REG.card_phash(c, idx) for c in pcards + scards)
    print(f"BARAJA    · {len(pcards)} posts + {len(scards)} stories en CAPTIONS.md")
    print(f"            {len(allf)} fotos DISTINTAS en total (lo que cuenta)")
    if noid:
        print(f"  ⚠️  {len(noid)} tarjetas SIN identidad (el motor las salta): {noid[:8]}")
    today = str(datetime.date.today())
    blk = REG.blocked_hashes(today)
    fresh = [p for p in allf if not REG.is_blocked(p, blk)[0]]
    print(f"HISTORIAL · {len(led)} publicaciones · {len(clusters(r.get('phash') for r in led))} fotos distintas")
    print(f"HOY       · {len(fresh)} fotos frescas → ~{len(fresh)//2} publicaciones (~{len(fresh)} dias) sin repetir")
    print(f"NECESIDAD · {NEED} fotos distintas para 360 dias · faltan {max(0, NEED - len(allf))}")
    return 0


def cmd_plan(n=60):
    m = engine(); idx = REG.load_index()
    led = list(REG.load_ledger())
    s = dict(json.load(open(os.path.join(LOCAL, ".daily_state.json"))))
    d = datetime.date.today()
    if s.get("last_date") == str(d):
        d += datetime.timedelta(days=1)
    rows, first_bad = [], None
    import io, contextlib
    for _ in range(n):
        while d.toordinal() % m.CYCLE_DIV != m.CYCLE_DAY:
            d += datetime.timedelta(days=1)
        today = str(d)
        blocked = REG.blocked_hashes(today, rows=led)
        with contextlib.redirect_stdout(io.StringIO()):
            pi, (pf, _), w1 = m.pick_fresh(m.POSTS, s["post"], "posts", blocked, idx)
            si, sf, w2 = m.pick_fresh(m.STORY_FILES, s["story"], "stories", blocked, idx,
                                      [REG.card_phash(f"posts/{pf}", idx)])
        pp, sp = REG.card_phash(f"posts/{pf}", idx), REG.card_phash(f"stories/{sf}", idx)
        rep = []
        # WHY la ventana y no "visto alguna vez": la regla es 360 dias (gotcha 4 de palacio).
        for kind, ph, card in (("POST", pp, pf), ("STORY", sp, sf)):
            bad, why = REG.is_blocked(ph, blocked)
            if bad:
                rep.append(f"{kind} {card}: {why}")
        if pp and sp and REG.same_photo(pp, sp):
            rep.append("post y story MISMA foto")
        if rep and not first_bad:
            first_bad = today
        rows.append((today, pf, sf, rep))
        for kind, card, ph in (("post", f"posts/{pf}", pp), ("story", f"stories/{sf}", sp)):
            led.append({"date": today, "kind": kind, "card": card, "phash": ph})
        s["post"], s["story"] = pi + 1, si + 1
        d += datetime.timedelta(days=1)
    bad = [r for r in rows if r[3]]
    print(f"SIMULACION de {n} publicaciones ({rows[0][0]} → {rows[-1][0]})")
    for r in rows[:12]:
        print(f"   {r[0]}  post {r[1]:38s} story {r[2]}")
    print(f"  repeticiones: {len(bad)}")
    for r in bad[:15]:
        print(f"   ⚠️  {r[0]}  {'; '.join(r[3])}")
    if first_bad:
        print(f"  BARAJA AGOTADA el {first_bad} (dentro de {(datetime.date.fromisoformat(first_bad)-datetime.date.today()).days} dias)")
    else:
        print("  ✅ ninguna foto repetida en toda la simulacion")
    return 1 if bad else 0


def cmd_add(kind, src, card):
    src = os.path.abspath(src)
    if not os.path.exists(src):
        print("ERROR: no existe", src); return 2
    idx = REG.load_index()
    md5 = hashlib.md5(open(src, "rb").read()).hexdigest()
    ph = REG.phash(src)
    for c, e in idx.items():
        if e.get("phash") and REG.same_photo(ph, e["phash"]):
            print(f"RECHAZADA: misma foto que {c} ({e['photo']})"); return 2
        p = e.get("src")
        if p and os.path.exists(p) and hashlib.md5(open(p, "rb").read()).hexdigest() == md5:
            print(f"RECHAZADA: byte a byte {c}"); return 2
    import make_manzanoshabitat as MK
    rel = os.path.relpath(src, MK.RAW)   # make_post trabaja relativo a raw/
    MK.make_post(rel, card, story=(kind == "story"))
    sub = "stories" if kind == "story" else "posts"
    idx[REG.key(f"{sub}/{card}")] = {"photo": os.path.relpath(src, LOCAL), "phash": ph,
                                     "src": src, "how": "add"}
    REG.save_index(idx)
    print(f"OK: {sub}/{card} ← {os.path.relpath(src, LOCAL)}")
    return 0


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] == "check":
        sys.exit(cmd_check())
    if a[0] == "plan":
        sys.exit(cmd_plan(int(a[1]) if len(a) > 1 else 60))
    if a[0] == "add" and len(a) == 4:
        sys.exit(cmd_add(a[1], a[2], a[3]))
    if a[0] == "reindex":
        REG.build_index(); sys.exit(0)
    print(__doc__); sys.exit(2)
