#!/bin/bash
# Refresca catalogs/streams y pushea a GitHub Pages (cada 5 min)
set -e
cd $HOME/stremio-live-addons
python3 tools/gen.py >> $HOME/.stremio-live-refresh.log 2>&1 || true
git add -A
git diff --cached --quiet && exit 0
git commit -m "refresh $(date -u +%FT%TZ)" >/dev/null 2>&1 || exit 0
CRED=$(python3 -c "
import pathlib,base64
cfg=pathlib.Path.home()/'.config/gh/hosts.yml'
tok=next((l.split(':',1)[1].strip() for l in cfg.read_text().splitlines() if l.strip().startswith(('oauth_token:','token:'))),'')
print(base64.b64encode(f'x-access-token:{tok}'.encode()).decode())
")
git -c "http.https://github.com/.extraheader=AUTHORIZATION: basic $CRED" push origin main >/dev/null 2>&1 || true
