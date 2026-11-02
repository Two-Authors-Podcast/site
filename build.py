#!/usr/bin/env python3
"""Build twoauthorspodcast.com from the Podbean RSS feed plus the corrected transcripts in /transcripts.

Every episode in the feed gets its own page automatically. When a file named
transcripts/s<season>e<episode>.txt exists, its transcript is added to that page.

Usage:
    python3 build.py                 # downloads the live feed
    python3 build.py --feed feed.xml # uses a saved copy of the feed
"""
import argparse, email.utils, html, json, os, re, shutil, sys, urllib.request
import xml.etree.ElementTree as ET
from datetime import timezone

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "_site")
CONFIG = json.load(open(os.path.join(ROOT, "config.json"), encoding="utf-8"))
NS = {
    "itunes": "http://www.itunes.com/dtds/podcast-1.0.dtd",
    "content": "http://purl.org/rss/1.0/modules/content/",
    "podcast": "https://podcastindex.org/namespace/1.0",
}
esc = lambda s: html.escape(s or "", quote=True)


def slugify(s):
    s = s.replace(" ", " ").lower()
    s = re.sub(r"&amp;|&", " and ", s)
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def inline(s):
    """Escape text and turn *phrase* into italics."""
    return re.sub(r"\*(.+?)\*", r"<em>\1</em>", html.escape(s, quote=False))


# ---------- Feed ----------

def load_feed(path):
    if path:
        return open(path, "rb").read()
    req = urllib.request.Request(CONFIG["feed_url"], headers={"User-Agent": "twoauthorspodcast.com site builder"})
    return urllib.request.urlopen(req, timeout=60).read()


def parse_feed(raw):
    channel = ET.fromstring(raw).find("channel")
    episodes = []
    for item in channel.findall("item"):
        g = lambda tag: (item.findtext(tag, default="", namespaces=NS) or "").strip()
        title = html.unescape(g("title")).replace(" ", " ")
        season, number = g("itunes:season"), g("itunes:episode")
        enc = item.find("enclosure")
        img = item.find("itunes:image", NS)
        dt = email.utils.parsedate_to_datetime(g("pubDate")) if g("pubDate") else None
        key = f"s{season}e{number}" if season and number else None
        slug = f"{key}-{slugify(title)}" if key else slugify(title)
        dur = g("itunes:duration")
        mins = None
        if dur.isdigit():
            mins = round(int(dur) / 60)
        elif ":" in dur:
            parts = [int(p) for p in dur.split(":")]
            secs = sum(p * 60 ** i for i, p in enumerate(reversed(parts)))
            mins = round(secs / 60)
        episodes.append({
            "title": title, "season": season, "number": number, "key": key, "slug": slug,
            "date": dt, "audio": enc.get("url") if enc is not None else "",
            "image": img.get("href") if img is not None else "",
            "notes_html": g("content:encoded") or g("description"),
            "summary": re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", g("itunes:summary") or g("description")))).strip(),
            "minutes": mins, "podbean_url": g("link"),
        })
    episodes.sort(key=lambda e: e["date"] or 0, reverse=True)
    return episodes


def first_paragraph(ep):
    """The opening description, before the standard Patreon and links block."""
    text = re.split(r"Support us on Patreon", ep["summary"])[0].strip()
    return text or ep["title"]


# ---------- Transcripts ----------

def load_transcript(ep):
    if not ep["key"]:
        return None
    path = os.path.join(ROOT, "transcripts", f"{ep['key']}.txt")
    if not os.path.exists(path):
        return None
    extra_path = os.path.join(ROOT, "transcripts", f"{ep['key']}.json")
    extra = json.load(open(extra_path, encoding="utf-8")) if os.path.exists(extra_path) else {}
    speakers = dict(CONFIG["speakers"])
    speakers.update(extra.get("speakers", {}))
    parts, contents, turn, n = [], [], None, 0

    def close():
        nonlocal turn
        if turn:
            who, paras, tid = turn
            name, is_guest = speakers.get(who, [who.title(), False])
            body = "".join(f"<p>{inline(p)}</p>" for p in paras)
            parts.append(f'<div class="turn" id="{tid}"><a class="cite" href="#{tid}" aria-label="Link to this passage">#</a>'
                         f'<div class="who{" guest" if is_guest else ""}">{esc(name)}</div><div class="said">{body}</div></div>')
        turn = None

    for line in open(path, encoding="utf-8").read().splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("## "):
            close()
            head = line[3:]
            sid = slugify(head)
            parts.append(f'<h3 id="{sid}">{inline(head)}</h3>')
            contents.append(f'<li><a href="#{sid}">{inline(head)}</a></li>')
            continue
        m = re.match(r"^([A-Z][A-Z0-9_]*): (.*)$", line)
        if m:
            close()
            n += 1
            turn = (m.group(1), [m.group(2)], f"t{n}")
        elif turn:
            turn[1].append(line)
    close()
    return {"html": "\n".join(parts), "contents": "".join(contents), "path": path, "extra": extra}


# ---------- Page shell ----------

def page(title, description, body, depth, canonical, json_ld=None, og_image=None):
    up = "../" * depth
    site = CONFIG["site_url"].rstrip("/")
    ld = f'<script type="application/ld+json">{json.dumps(json_ld, ensure_ascii=False)}</script>' if json_ld else ""
    img = og_image or f"{site}/assets/show-logo.jpg"
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}">
<link rel="canonical" href="{esc(canonical)}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(description)}">
<meta property="og:image" content="{esc(img)}">
<meta property="og:url" content="{esc(canonical)}">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="{up}assets/show-logo.jpg">
<link rel="alternate" type="application/rss+xml" title="{esc(CONFIG['show_title'])}" href="{esc(CONFIG['feed_url'])}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Anton&family=Barlow:wght@500;600;700&family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,600;1,8..60,400&display=swap">
<link rel="stylesheet" href="{up}assets/site.css">
{ld}
</head>
<body>
<header class="masthead">
  <div class="wrap">
    <a class="brand" href="{up}index.html"><img src="{up}assets/show-logo.jpg" alt="" width="48" height="48"><span>{esc(CONFIG['show_title'])}</span></a>
    <nav class="nav" aria-label="Site"><a href="{up}index.html#episodes">Episodes</a><a href="{up}index.html#about">About</a><a href="{esc(CONFIG['listen_links'][0][1])}">Subscribe</a></nav>
  </div>
</header>
<div class="sponsor">presented by <a href="http://tryvellum.com/twoauthors">Vellum</a></div>
{body}
<footer>
  <div class="wrap">
    <span>{esc(CONFIG['show_title'])} with Douglas Pratt and Nicholas Harvey</span>
    <span>Contact: {esc(CONFIG['contact_email'])}</span>
  </div>
</footer>
</body>
</html>
"""


def fmt_date(dt):
    return f"{dt.day} {dt.strftime('%B %Y')}" if dt else ""


def ep_label(ep):
    bits = []
    if ep["key"]:
        bits.append(f"Season {ep['season']} · Episode {ep['number']}")
    if ep["date"]:
        bits.append(fmt_date(ep["date"]))
    return " · ".join(bits)


# ---------- Episode page ----------

COPY_SCRIPT = """<script>
(function () {
  var btn = document.getElementById('copy-transcript');
  if (!btn) return;
  var status = document.getElementById('copy-status');
  var body = document.getElementById('transcript-body');
  function plainText() {
    var out = [];
    body.querySelectorAll('h3, .turn').forEach(function (el) {
      if (el.tagName === 'H3') { out.push('\\n' + el.textContent.trim().toUpperCase() + '\\n'); return; }
      var who = el.querySelector('.who').textContent.trim();
      var paras = Array.prototype.map.call(el.querySelectorAll('.said p'), function (p) { return p.textContent.trim(); });
      out.push(who + ': ' + paras.join('\\n\\n'));
    });
    return out.join('\\n\\n').trim();
  }
  btn.addEventListener('click', function () {
    var text = plainText();
    function fallback() {
      var range = document.createRange(); range.selectNodeContents(body);
      var sel = window.getSelection(); sel.removeAllRanges(); sel.addRange(range);
      status.textContent = 'Transcript selected. Press Ctrl+C or Cmd+C to copy it.';
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(function () { status.textContent = 'Copied.'; }, fallback);
    } else { fallback(); }
  });
})();
</script>"""


def episode_page(ep, tr):
    site = CONFIG["site_url"].rstrip("/")
    url = f"{site}/episodes/{ep['slug']}/"
    topic, guest = (ep["title"].rsplit(" with ", 1) + [None])[:2] if " with " in ep["title"] else (ep["title"], None)
    h1 = f"{inline(topic)}<span class=\"guest\">with {inline(guest)}</span>" if guest else inline(ep["title"])
    summary = first_paragraph(ep)
    art = ep["image"] or "../../assets/show-logo.jpg"
    listen = "".join(f'<a class="btn" href="{esc(u)}">{esc(t)}</a>' for t, u in CONFIG["listen_links"][:5])
    mins = f" · {ep['minutes']} minutes" if ep["minutes"] else ""

    transcript_block, aside = "", ""
    if tr:
        bio = tr["extra"].get("guest_bio_html", "")
        transcript_block = f"""
      <section id="transcript">
        <div class="transcript-head">
          <h2 class="big">Transcript</h2>
          <div><button class="btn" id="copy-transcript" type="button">Copy transcript</button> <span class="toast" id="copy-status" role="status"></span></div>
        </div>
        <p class="about-transcript">This transcript was produced automatically and edited for readability, with filler words and false starts removed. Please check quotations against the audio before publishing them. Each passage has its own link for citing. <a href="transcript.txt">Download the transcript as plain text.</a></p>
        <div class="transcript" id="transcript-body">
{tr['html']}
        </div>
      </section>"""
        aside = f'<aside><div class="contents"><h2>In this episode</h2><ol>{tr["contents"]}</ol></div></aside>'
        if bio:
            transcript_block = f'<section class="prose"><h2 class="big">About the guest</h2>{bio}</section>' + transcript_block

    body = f"""
<div class="hero" id="top">
  <div class="wrap">
    <img src="{esc(art)}" alt="Episode artwork for {esc(ep['title'])}" width="300" height="300">
    <div>
      <p class="eyebrow">{esc(ep_label(ep))}{esc(mins)}</p>
      <h1>{h1}</h1>
      <p class="standfirst">{esc(summary)}</p>
      <audio controls preload="none" src="{esc(ep['audio'])}"></audio>
      <div class="listen">{listen}{'<a class="btn" href="#transcript">Read the transcript</a>' if tr else ''}</div>
    </div>
  </div>
</div>
<div class="body">
  <div class="wrap"{' style="grid-template-columns: minmax(0, 1fr)"' if not tr else ''}>
    <main>
      <section>
        <h2 class="big">Show notes</h2>
        <div class="shownotes">{ep['notes_html']}</div>
      </section>
      {transcript_block}
    </main>
    {aside}
  </div>
</div>
{COPY_SCRIPT if tr else ''}"""

    ld = {
        "@context": "https://schema.org", "@type": "PodcastEpisode", "name": ep["title"], "url": url,
        "description": summary,
        "datePublished": ep["date"].astimezone(timezone.utc).date().isoformat() if ep["date"] else None,
        "associatedMedia": {"@type": "MediaObject", "contentUrl": ep["audio"]},
        "partOfSeries": {"@type": "PodcastSeries", "name": CONFIG["show_title"], "url": site + "/"},
    }
    if ep["key"]:
        ld["episodeNumber"] = ep["number"]
        ld["partOfSeason"] = {"@type": "PodcastSeason", "seasonNumber": ep["season"]}
    if tr:
        ld["transcript"] = url + "transcript.txt"
    return page(f"{ep['title']} | {CONFIG['show_title']}", summary, body, 2, url, ld, ep["image"] or None)


# ---------- Home page ----------

def home_page(episodes, has_tr):
    site = CONFIG["site_url"].rstrip("/") + "/"
    latest = episodes[0]
    cards = []
    for ep in episodes:
        badge = '<span class="badge">Transcript</span>' if ep["slug"] in has_tr else ""
        img = esc(ep["image"] or "assets/show-logo.jpg")
        cards.append(f'<li class="ep-card" data-search="{esc(ep["title"].lower())}"><a href="episodes/{ep["slug"]}/">'
                     f'<img src="{img}" alt="" loading="lazy" width="220" height="220">'
                     f'<span class="meta">{esc(ep_label(ep))}</span><span class="t">{esc(ep["title"])}{badge}</span></a></li>')
    listen = "".join(f'<a class="btn{" primary" if i == 0 else ""}" href="{esc(u)}">{esc(t)}</a>' for i, (t, u) in enumerate(CONFIG["listen_links"]))
    body = f"""
<div class="home-hero">
  <div class="wrap">
    <img src="assets/show-logo.jpg" alt="{esc(CONFIG['show_title'])} logo" width="260" height="260">
    <div>
      <p class="eyebrow">Douglas Pratt &amp; Nicholas Harvey</p>
      <h1>{esc(CONFIG['show_title'])}</h1>
      <p class="standfirst">{esc(CONFIG['show_description'])}</p>
      <div class="listen">{listen}</div>
    </div>
  </div>
</div>
<section class="latest" aria-label="Latest episode">
  <div class="wrap">
    <a href="episodes/{latest['slug']}/"><img src="{esc(latest['image'] or 'assets/show-logo.jpg')}" alt="" width="200" height="200"></a>
    <div>
      <p class="eyebrow">Latest episode · {esc(ep_label(latest))}</p>
      <h2><a href="episodes/{latest['slug']}/">{esc(latest['title'])}</a></h2>
      <p class="standfirst">{esc(first_paragraph(latest))}</p>
      <audio controls preload="none" src="{esc(latest['audio'])}"></audio>
    </div>
  </div>
</section>
<section class="episodes" id="episodes">
  <div class="wrap">
    <div class="episodes-head">
      <h2 class="big">All episodes</h2>
      <label for="episode-search" class="section-label" style="position:absolute;left:-9999px">Search episodes</label>
      <input id="episode-search" type="search" placeholder="Search by guest or topic">
    </div>
    <ul class="ep-grid" id="ep-grid">{''.join(cards)}</ul>
    <p class="no-results" id="no-results" hidden>No episodes match that search.</p>
  </div>
</section>
<section class="episodes" id="about" style="background: var(--wash)">
  <div class="wrap prose">
    <h2 class="big">About the show</h2>
    {CONFIG['about_html']}
  </div>
</section>
<script>
(function () {{
  var input = document.getElementById('episode-search');
  var cards = document.querySelectorAll('#ep-grid .ep-card');
  var none = document.getElementById('no-results');
  input.addEventListener('input', function () {{
    var q = input.value.trim().toLowerCase(), shown = 0;
    cards.forEach(function (c) {{ var m = !q || c.dataset.search.indexOf(q) !== -1; c.hidden = !m; if (m) shown++; }});
    none.hidden = shown !== 0;
  }});
}})();
</script>"""
    ld = {"@context": "https://schema.org", "@type": "PodcastSeries", "name": CONFIG["show_title"], "url": site,
          "description": CONFIG["show_description"], "webFeed": CONFIG["feed_url"]}
    return page(CONFIG["show_title"], CONFIG["show_description"], body, 0, site, ld)


# ---------- Build ----------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--feed", help="path to a saved copy of the RSS feed")
    args = ap.parse_args()
    episodes = parse_feed(load_feed(args.feed))
    if not episodes:
        sys.exit("The feed has no episodes, so nothing was built.")
    if os.path.exists(OUT):
        shutil.rmtree(OUT)
    shutil.copytree(os.path.join(ROOT, "assets"), os.path.join(OUT, "assets"))
    has_tr, urls = set(), [CONFIG["site_url"].rstrip("/") + "/"]
    for ep in episodes:
        tr = load_transcript(ep)
        d = os.path.join(OUT, "episodes", ep["slug"])
        os.makedirs(d, exist_ok=True)
        open(os.path.join(d, "index.html"), "w", encoding="utf-8").write(episode_page(ep, tr))
        if tr:
            has_tr.add(ep["slug"])
            shutil.copy(tr["path"], os.path.join(d, "transcript.txt"))
        urls.append(f"{CONFIG['site_url'].rstrip('/')}/episodes/{ep['slug']}/")
    open(os.path.join(OUT, "index.html"), "w", encoding="utf-8").write(home_page(episodes, has_tr))
    open(os.path.join(OUT, "sitemap.xml"), "w").write(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"  <url><loc>{esc(u)}</loc></url>\n" for u in urls) + "</urlset>\n")
    open(os.path.join(OUT, "robots.txt"), "w").write(f"User-agent: *\nAllow: /\nSitemap: {CONFIG['site_url'].rstrip('/')}/sitemap.xml\n")
    open(os.path.join(OUT, ".nojekyll"), "w").write("")
    if os.path.exists(os.path.join(ROOT, "CNAME")):
        shutil.copy(os.path.join(ROOT, "CNAME"), os.path.join(OUT, "CNAME"))
    print(f"Built {len(episodes)} episode pages, {len(has_tr)} with transcripts.")


if __name__ == "__main__":
    main()
