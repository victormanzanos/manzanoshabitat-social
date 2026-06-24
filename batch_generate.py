#!/usr/bin/env python3
"""Genera todas las imágenes branded (posts 1080x1350 + stories 1080x1920)."""
import sys, os
sys.path.insert(0, os.path.expanduser("~/manzanoshabitat-social"))
from make_manzanoshabitat import make_post

# (src_rel, out_name) — posts de proyectos + zonas + blog
POSTS = [
    # ---- Proyectos en venta ----
    ("villafranca/hero.jpg",        "01-villafranca.jpg"),
    ("azagra/night.jpg",            "02-azagra.jpg"),
    ("sanadrian/hero-building.jpg", "03-sanadrian.jpg"),
    ("grande28/cavas.jpg",          "04-grande28-fachada.jpg"),
    ("grande28/rooftop.jpg",        "05-grande28-rooftop.jpg"),
    ("haro/hero.jpg",               "06-haro.jpg"),
    ("entrerios/hero.jpg",          "07-entrerios.jpg"),
    ("azagra/birdseye.jpg",         "08-azagra-aerea.jpg"),
    ("sanadrian/render.jpg",        "09-sanadrian-plaza.jpg"),
    ("grande28/salon.jpg",          "10-grande28-salon.jpg"),
    ("villafranca/v07.jpg",         "11-villafranca-detalle.jpg"),
    ("grande28/piscina.jpg",        "12-grande28-spa.jpg"),
    ("azagra/night2.jpg",           "13-azagra-noche.jpg"),
    ("sanadrian/v5.jpg",            "14-sanadrian-vida.jpg"),
    ("grande28/hero.jpg",           "15-grande28-lujo.jpg"),
    # ---- Zonas / estilo de vida ----
    ("blog/calahorra-catedral.jpg", "16-calahorra.jpg"),
    ("blog/tudela-ribera.jpg",      "17-ribera-navarra.jpg"),
    ("blog/haro.jpg",               "18-larioja.jpg"),
    # ---- Blog / valor ----
    ("blog/aerotermia.jpg",         "19-aerotermia.jpg"),
    ("blog/comprar-sobre-plano.jpg","20-sobre-plano.jpg"),
]
STORIES = [
    ("villafranca/hero.jpg",        "01-villafranca-story.jpg"),
    ("azagra/night3.jpg",           "02-azagra-story.jpg"),
    ("grande28/rooftop.jpg",        "03-grande28-story.jpg"),
    ("sanadrian/hero-building.jpg", "04-sanadrian-story.jpg"),
    ("haro/hero.jpg",               "05-haro-story.jpg"),
    ("grande28/piscina.jpg",        "06-grande28-spa-story.jpg"),
    ("blog/calahorra-catedral.jpg", "07-calahorra-story.jpg"),
    ("entrerios/hero.jpg",          "08-entrerios-story.jpg"),
]
ok = 0
for src, out in POSTS:
    try:
        make_post(src, out, story=False); ok += 1
    except Exception as e:
        print(f"  ✗ {src}: {e}")
for src, out in STORIES:
    try:
        make_post(src, out, story=True); ok += 1
    except Exception as e:
        print(f"  ✗ {src}: {e}")
print(f"\nGenerados {ok}/{len(POSTS)+len(STORIES)} ({len(POSTS)} posts + {len(STORIES)} stories)")
