# Manzanos Hábitat — Instagram daily engine (@manzanoshabitat)

Motor de publicación automática en Instagram, clonado de @palaciodemanzanos /
@manzanoswinesusa. Publica **1 día sí, 1 día no** (días PARES) a horas variables,
con imágenes de recuadro dorado + logo Manzanos Hábitat.

## Arquitectura
- `daily_engine.py` — motor idempotente (1 post/día). Publica post + story, rota
  por CAPTIONS.md, baraja hashtags (anti-patrón Meta), jitter + defer aleatorio.
- `make_manzanoshabitat.py` — generador de imágenes (marco dorado doble + acentos
  art-déco + logo MH abajo). `batch_generate.py` genera todo el lote.
- `CAPTIONS.md` — single source of truth: 24 posts + 8 stories. Contenido =
  proyectos en venta + zonas/estilo de vida + blog, con motivación de emprender.
- `refresh_token.py` — renueva el token (~60 días) los domingos.
- Repo público de imágenes: github.com/victormanzanos/manzanoshabitat-social

## Cadencia (no colisiona con otras cuentas)
- Manzanos Hábitat: días PARES (ordinal%2==0), horas 12:08/14:41/16:53/18:37
- Palacio: días impares · Manzanos Wines: %4==0 · JMC: %4==2

## Credenciales (Keychain)
- `MANZANOSHABITAT_IG_ACCESS_TOKEN` (long-lived, IGAA...)
- `MANZANOSHABITAT_IG_ACCOUNT_ID` (Instagram account id, 17 dígitos)

## Puesta en marcha (cuando el token esté en Keychain)
```bash
# 1. Verificar que el token apunta a @manzanoshabitat
python3 -c "import subprocess,urllib.request,json; t=subprocess.check_output(['$HOME/Code/CyberSecurity/scripts/secrets.sh','get','MANZANOSHABITAT_IG_ACCESS_TOKEN']).decode().strip(); print(json.load(urllib.request.urlopen(f'https://graph.instagram.com/v23.0/me?fields=username&access_token={t}')))"
# 2. Test (publica de verdad, salta la guardia de día)
FORCE=1 python3 ~/manzanoshabitat-social/daily_engine.py
# 3. Cargar los LaunchAgents
cp ~/manzanoshabitat-social/com.manzanoshabitat.dailyig.plist ~/Library/LaunchAgents/
cp ~/manzanoshabitat-social/com.manzanoshabitat.igtokenrefresh.plist ~/Library/LaunchAgents/
launchctl load -w ~/Library/LaunchAgents/com.manzanoshabitat.dailyig.plist
launchctl load -w ~/Library/LaunchAgents/com.manzanoshabitat.igtokenrefresh.plist
```

## Añadir/cambiar contenido
- Editar `CAPTIONS.md` (texto) y regenerar imágenes con `batch_generate.py`.
- Foto real (sin marco): dejar `.jpg` (+ opcional `.txt` caption) en `reales/` —
  el motor publica 1 real cada 3 posts de marca y la archiva en `reales/published/`.
- Tras cambiar imágenes: `git add -A && git commit && git push` (Instagram las lee
  del repo público vía raw.githubusercontent.com).

## Watchdog
Scheduled-task `manzanoshabitat-ig-daily-check` (cada noche 21:24) verifica que el
post salió y lo recupera si no. NO publica nada por su cuenta salvo ejecutar el motor.
