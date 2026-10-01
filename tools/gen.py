#!/usr/bin/env python3
"""Genera catalogs, streams y meta de Twitch y Kick para Stremio.
Corre cada 5 minutos via GitHub Actions (tokens de reproduccion frescos)."""
import json
import pathlib
import shutil
import time
import urllib.parse
import urllib.request

CID = "kimne78kx3ncx6brgo4mv6wki5h1ko"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
ROOT = pathlib.Path(__file__).resolve().parent.parent

KICK_SLUGS = [
    "xqc", "adinross", "trainwreckstv", "hasanabi", "westcol", "ibai",
    "loltyler1", "kaicenat", "forsen", "roshtein", "elxokas", "lathyrx",
    "jynxzi", "clix", "summit1g", "shroud", "s1mple", "gaules",
    "thebausffs", "bagels", "slakun", "grimmgreen", "adamaris", "tectone",
    "auronplay", "missjoy", "xseira", "ludwig", "nickmercs", "pokimane",
    "sodapoppin", "tarik", "valorant", "caedrel", "kaiicenat",
    "moistcr1tikal", "asmongold", "buddha", "jbags", "jerma985",
    "moonmoon", "quin69", "timthetatman", "scump",
]


def http(url, headers=None, data=None, timeout=15):
    req = urllib.request.Request(url, data=data,
                                 headers={"User-Agent": UA, **(headers or {})})
    return urllib.request.urlopen(req, timeout=timeout).read()


def gql(query, variables=None):
    payload = {"query": query}
    if variables:
        payload["variables"] = variables
    body = json.dumps(payload).encode()
    return json.loads(http("https://gql.twitch.tv/gql", {
        "Client-ID": CID, "Content-Type": "application/json"}, body))


def write(rel, obj):
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False))
    print("wrote", rel)


def clean():
    for d in ("stream/tv", "meta/tv"):
        p = ROOT / d
        if p.exists():
            shutil.rmtree(p)


def twitch_usher(login):
    tok = gql(
        "query($login:String!){streamPlaybackAccessToken(channelName:$login,"
        "params:{platform:\"web\",playerBackend:\"mediaplayer\",playerType:\"site\"})"
        "{value signature}}", {"login": login})
    data = (tok.get("data") or {}).get("streamPlaybackAccessToken")
    if not data:
        return None
    qs = urllib.parse.urlencode({
        "allow_source": True, "allow_audio_only": True, "fast_bread": True,
        "player_backend": "mediaplayer", "supported_codecs": "avc1",
        "sig": data["signature"], "token": data["value"]})
    return f"https://usher.ttvnw.net/api/channel/hls/{login}.m3u8?{qs}"


def gen_twitch():
    q = ("{streams(first:30){edges{node{title viewersCount "
         "broadcaster{login displayName profileImageURL(width:300)} "
         "game{name}}}}}")
    r = gql(q)
    edges = ((r.get("data") or {}).get("streams") or {}).get("edges") or []
    nodes = [e["node"] for e in edges]
    nodes.sort(key=lambda n: n.get("viewersCount") or 0, reverse=True)

    catalog = []
    for n in nodes:
        b = n["broadcaster"]
        login = b["login"]
        viewers = n.get("viewersCount") or 0
        game = (n.get("game") or {}).get("name") or ""
        title = n.get("title") or ""
        desc = f"{title}\n{viewers:,} viewers · {game}"
        entry = {
            "id": f"twitch_{login}",
            "type": "tv",
            "name": b.get("displayName") or login,
            "poster": b.get("profileImageURL") or "",
            "posterShape": "landscape",
            "logo": b.get("profileImageURL") or "",
            "description": desc,
            "background": b.get("profileImageURL") or "",
        }
        catalog.append(entry)
        write(f"meta/tv/twitch_{login}.json", {
            "id": f"twitch_{login}", "type": "tv", "name": entry["name"],
            "poster": entry["poster"], "logo": entry["logo"],
            "posterShape": "landscape", "description": desc})
        try:
            url = twitch_usher(login)
        except Exception as e:
            print("usher fail", login, e)
            url = None
        if url:
            write(f"stream/tv/twitch_{login}.json", {"streams": [{
                "url": url,
                "name": "Twitch",
                "title": f"{game} — {viewers:,} viewers",
                "behaviorHints": {"bingeGroup": "twitch-live"}}]})

    write("catalog/tv/twitch_top.json", {"metas": catalog})
    print("twitch live:", len(catalog))


def kick_channel(slug):
    req = urllib.request.Request(f"https://kick.com/api/v2/channels/{slug}",
        headers={"User-Agent": UA, "Accept": "application/json",
                 "Accept-Language": "en-US,en;q=0.9",
                 "Referer": f"https://kick.com/{slug}",
                 "Origin": "https://kick.com"})
    return json.load(urllib.request.urlopen(req, timeout=12))


def gen_kick():
    catalog, seen = [], set()
    for slug in KICK_SLUGS:
        if slug in seen:
            continue
        seen.add(slug)
        try:
            ch = kick_channel(slug)
        except Exception as e:
            print("kick fail", slug, e)
            time.sleep(1.5)
            continue
        time.sleep(1.2)
        live = ch.get("livestream")
        if not live or not ch.get("playback_url"):
            continue
        user = ch.get("user") or {}
        name = user.get("username") or slug
        s_title = live.get("session_title") or ""
        viewers = live.get("viewer_count") or 0
        cats = ch.get("recent_categories") or []
        game = (cats[0].get("name") if cats else "") or ""
        poster = (live.get("thumbnail") or {}).get("url") or user.get("profile_pic") or ""
        desc = f"{s_title}\n{viewers:,} viewers · {game}"
        entry = {
            "id": f"kick_{slug}", "type": "tv", "name": name,
            "poster": poster, "posterShape": "landscape",
            "logo": user.get("profile_pic") or "",
            "description": desc, "background": poster,
        }
        catalog.append(entry)
        write(f"meta/tv/kick_{slug}.json", {
            "id": f"kick_{slug}", "type": "tv", "name": name,
            "poster": poster, "logo": entry["logo"],
            "posterShape": "landscape", "description": desc})
        write(f"stream/tv/kick_{slug}.json", {"streams": [{
            "url": ch["playback_url"],
            "name": "Kick",
            "title": f"{game} — {viewers:,} viewers",
            "behaviorHints": {"bingeGroup": "kick-live"}}]})

    write("catalog/tv/kick_live.json", {"metas": catalog})
    print("kick live:", len(catalog))


if __name__ == "__main__":
    clean()
    try:
        gen_twitch()
    except Exception as e:
        print("TWTICH ERROR", e)
    try:
        gen_kick()
    except Exception as e:
        print("KICK ERROR", e)
    # fallback: si un catalog quedo vacio, dejar archivo valido vacio
    for rel in ("catalog/tv/twitch_top.json", "catalog/tv/kick_live.json"):
        if not (ROOT / rel).exists():
            write(rel, {"metas": []})
