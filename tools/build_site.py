#!/usr/bin/env python3
"""
Build the Book Club website into _site/ from the files in content/.

    pip install -r tools/requirements.txt
    python3 tools/build_site.py
    python3 -m http.server 8000 --directory _site      # preview at http://127.0.0.1:8000

Coordinators normally never run this: the admin panel saves to GitHub and a
GitHub Action runs it automatically. The output in _site/ is plain HTML that
can be uploaded to the IITK server as-is.
"""
import datetime
import html
import json
import os
import re
import shutil
import sys
import urllib.parse

import yaml
from PIL import Image, ImageOps

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
CONTENT = os.path.join(ROOT, "content")
OUT = os.path.join(ROOT, "_site")
IMG_EXT = (".jpg", ".jpeg", ".png", ".webp", ".gif")

I = {
    "search": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.6-3.6"/></svg>',
    "sun": '<svg class="sun" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" aria-hidden="true"><circle cx="12" cy="12" r="4.2"/><path d="M12 2.5v2.2M12 19.3v2.2M4.6 4.6l1.6 1.6M17.8 17.8l1.6 1.6M2.5 12h2.2M19.3 12h2.2M4.6 19.4l1.6-1.6M17.8 6.2l1.6-1.6"/></svg>',
    "moon": '<svg class="moon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5Z"/></svg>',
    "menu": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" aria-hidden="true"><path d="M4 7h16M4 12h16M4 17h10"/></svg>',
    "arrow": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 12h14M13 6l6 6-6 6"/></svg>',
    "clock": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" aria-hidden="true"><circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/></svg>',
    "quill": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 4c-7 0-12 5-13 12l-2 4M7 16c4 0 9-2 11-8"/></svg>',
    "book": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v15H6.5A2.5 2.5 0 0 0 4 20.5v-15Z"/><path d="M4 20.5A2.5 2.5 0 0 0 6.5 23H20v-5"/></svg>',
    "expand": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M14 4h6v6M10 20H4v-6M20 4l-7 7M4 20l7-7"/></svg>',
    "instagram": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="5"/><circle cx="12" cy="12" r="4"/><circle cx="17.5" cy="6.5" r="1" fill="currentColor" stroke="none"/></svg>',
    "facebook": '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M13.5 21v-7.5h2.6l.4-3h-3V8.6c0-.9.3-1.5 1.5-1.5h1.6V4.4c-.3 0-1.2-.1-2.3-.1-2.3 0-3.9 1.4-3.9 4v2.2H7.8v3h2.6V21h3.1Z"/></svg>',
    "discord": '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M19.3 5.4A16.6 16.6 0 0 0 15.2 4l-.5 1a15.4 15.4 0 0 0-5.4 0l-.5-1a16.5 16.5 0 0 0-4.1 1.4C2.1 9.3 1.4 13.1 1.8 16.9a16.7 16.7 0 0 0 5 2.5l1.1-1.7c-.6-.2-1.2-.5-1.7-.8l.4-.3a11.9 11.9 0 0 0 10.8 0l.4.3c-.5.3-1.1.6-1.7.8l1.1 1.7a16.6 16.6 0 0 0 5-2.5c.5-4.4-.8-8.2-2.9-11.5ZM8.7 14.6c-1 0-1.8-.9-1.8-2s.8-2 1.8-2 1.8.9 1.8 2-.8 2-1.8 2Zm6.6 0c-1 0-1.8-.9-1.8-2s.8-2 1.8-2 1.8.9 1.8 2-.8 2-1.8 2Z"/></svg>',
}


FONTS = "https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,500;0,600;0,700;1,400;1,500;1,600&family=EB+Garamond:ital,wght@0,400;0,500;0,600;1,400;1,500&display=swap"

NAV = [
    ("index.html", "Home"),
    ("rules.html", "Rules"),
    ("catalogue.html", "Catalogue"),
    ("request.html", "Request a Book"),
    ("blogs.html", "Blogs"),
    ("contact.html", "Contact Us"),
    ("mellifluous.html", "Mellifluous"),
]
RESERVED = {h for h, _ in NAV} | {"404.html"}

# Genre spines on the home-page shelf: label, catalogue genre, colour, height %, width px
SPINES = [
    ("Fiction", "Fiction", "#7d1f2c", 90, 52),
    ("Classics", "Classics", "#2f4b3c", 97, 46),
    ("Fantasy", "Fantasy", "#23395b", 82, 50),
    ("Poetry", "Poetry", "#8a5a2b", 74, 38),
    ("Science Fiction", "Science Fiction", "#3b3b3b", 100, 54),
    ("Romance", "Romance", "#9b3b4b", 79, 42),
    ("Biographies", "Biographies", "#46523a", 92, 48),
    ("Drama", "Drama", "#4a2c4f", 70, 40),
    ("Self Help", "Self Help", "#6b4a1f", 84, 44),
    ("Bengali", "Bengali", "#1f4a4a", 88, 46),
    ("Hindi", "Hindi", "#7a3420", 80, 44),
]
# Genres listed in "About us" under a different name in the catalogue
GENRE_ALIAS = {"Comics": "Graphic Novels", "Popular Science": "Science"}
CATALOGUE_GENRES = set()   # filled in main() from data/catalogue.json

warnings = []


# ------------------------------------------------------------------ helpers
def esc(s):
    return html.escape(str(s or ""), quote=True)


def safe_url(url, where, web_only=False):
    """Allow only web, email and same-site links (no javascript: and the like)."""
    url = re.sub(r"[\x00-\x20]", "", str(url or ""))
    if not url:
        return ""
    if re.match(r"https?://", url, re.I) or (not web_only and (url.lower().startswith("mailto:")
                                                              or not re.match(r"[a-z][a-z0-9+.-]*:", url, re.I))):
        return url
    warnings.append(f"{where}: link '{url}' was left out (only https:// links are allowed here)")
    return ""


def form_open(site, subject):
    """Opening of a Web3Forms form. Submissions are emailed to the address the access key was made for."""
    key = str(site.get("web3forms_key") or "").strip()
    if not re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", key, re.I):
        msg = "site.json: no valid Web3Forms access key, so the forms will not send"
        if msg not in warnings:
            warnings.append(msg)
    return (f'<form action="https://api.web3forms.com/submit" method="post" data-ajax-form>\n'
            f'          <input type="hidden" name="access_key" value="{esc(key)}">\n'
            f'          <input type="hidden" name="subject" value="{esc(subject)}">\n'
            f'          <input type="hidden" name="from_name" value="Book Club website">\n'
            f'          <input type="checkbox" name="botcheck" class="hp" tabindex="-1" autocomplete="off" aria-hidden="true">')


def load_json(name):
    with open(os.path.join(CONTENT, name), encoding="utf-8") as fh:
        return json.load(fh)


def inline_md(text):
    """Inline Markdown: links, bold, italics, code. Input is plain text."""
    s = html.escape(str(text or ""), quote=False)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)",
               lambda m: (f'<a href="{safe_url(m.group(2), "Text link").replace(chr(34), "&quot;")}">{m.group(1)}</a>'
                          if safe_url(m.group(2), "Text link") else m.group(1)), s)
    s = re.sub(r"(\*\*|__)(.+?)\1", r"<strong>\2</strong>", s)
    s = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", s)
    s = re.sub(r"(?<![\w_])_(?!\s)(.+?)(?<!\s)_(?![\w_])", r"<em>\1</em>", s)
    s = s.replace("₹", '<span class="rs">₹</span>')
    return s


def is_pull_quote(text):
    plain = re.sub(r"[*_]", "", text).strip()
    return plain.startswith("“") and plain.endswith(("”", "…”", "...”")) and len(plain) < 260


def markdown(md, pull_quotes=False):
    """Small Markdown converter for blog posts: paragraphs, quotes, headings, lists."""
    out = []
    for block in re.split(r"\n\s*\n", (md or "").strip().replace("\r\n", "\n")):
        lines = [l.rstrip() for l in block.split("\n") if l.strip()]
        if not lines:
            continue
        first = lines[0].lstrip()
        if all(l.lstrip().startswith(">") for l in lines):
            text = " ".join(re.sub(r"^\s*>\s?", "", l) for l in lines)
            out.append(f"<blockquote>{inline_md(text)}</blockquote>")
        elif re.match(r"#{1,6}\s", first):
            level = min(len(first) - len(first.lstrip("#")) + 1, 4)
            out.append(f"<h{level}>{inline_md(first.lstrip('#').strip())}</h{level}>")
        elif all(re.match(r"\s*([-*+]|\d+[.)])\s", l) for l in lines):
            tag = "ol" if re.match(r"\s*\d", first) else "ul"
            items = "".join(f"<li>{inline_md(re.sub(r'^\s*([-*+]|\d+[.)])\s+', '', l))}</li>" for l in lines)
            out.append(f"<{tag}>{items}</{tag}>")
        else:
            text = " ".join(l.strip() for l in lines)
            text = re.sub(r"\\$", "", text)
            if pull_quotes and is_pull_quote(text):
                inner = re.sub(r"^\*(.*)\*$", r"\1", text)
                out.append(f'<p class="pull">{inline_md(inner)}</p>')
            else:
                out.append(f"<p>{inline_md(text)}</p>")
    return out


def asset_path(p):
    """Normalise an image path from the content files to a relative site path."""
    p = (p or "").strip()
    if not p or re.match(r"^https?://", p):
        return p
    p = re.sub(r"^(\.\./|\./|/)+", "", p)
    return p


def asset_exists(p):
    return bool(p) and (p.startswith("http") or os.path.isfile(os.path.join(ROOT, p)))


def socials(site, cls="socials"):
    items = [("Instagram", site["socials"].get("instagram"), "instagram"),
             ("Facebook", site["socials"].get("facebook"), "facebook"),
             ("Discord", site["socials"].get("discord"), "discord")]
    links = []
    for name, url, icon in items:
        url = safe_url(url, f"{name} link", web_only=True)
        if not url:
            continue
        label = f"<span>{name}</span>" if cls == "socials" else ""
        links.append(f'<a href="{esc(url)}" target="_blank" rel="noopener" aria-label="{name}">{I[icon]}{label}</a>')
    return f'<div class="{cls}">' + "".join(links) + "</div>"


def nowrap_room(location):
    """Keep 'Room Number 104, OAT' together on one line."""
    m = re.search(r"(Room.*)$", location)
    if not m:
        return esc(location)
    return esc(location[:m.start()]) + f'<span style="white-space:nowrap">{esc(m.group(1))}</span>'


# ------------------------------------------------------------------ layout
def head(title, desc):
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(title)}</title>
  <meta name="description" content="{esc(desc)}">
  <meta name="theme-color" content="#f7f0e1">
  <meta property="og:title" content="{esc(title)}">
  <meta property="og:description" content="{esc(desc)}">
  <meta property="og:image" content="assets/img/og-image.jpg">
  <link rel="icon" type="image/png" sizes="32x32" href="assets/img/favicon-32.png">
  <link rel="icon" type="image/png" sizes="192x192" href="assets/img/favicon-192.png">
  <link rel="apple-touch-icon" href="assets/img/apple-touch-icon.png">
  <script>try{{var t=localStorage.getItem("bc-theme");if(t)document.documentElement.setAttribute("data-theme",t)}}catch(e){{}}</script>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link rel="stylesheet" href="{FONTS}">
  <link rel="stylesheet" href="assets/css/style.css">
</head>"""


def header(site, active):
    cur = ' aria-current="page"'
    items = "\n".join(
        f'          <li><a href="{esc(href)}"{cur if href == active else ""}>{label}</a></li>'
        for href, label in NAV)
    t = site["timings"]
    return f"""<body>
  <a class="skip" href="#main">Skip to content</a>
  <div class="topline">
    <div class="wrap">
      <span class="council">{esc(site["council"])}</span>
      <span class="hours"><i class="dot" aria-hidden="true"></i><span>Mon – Thu · {esc(t["weekdays"])}</span><i class="sep" aria-hidden="true">·</i><span>Fri – Sun · {esc(t["weekends"])}</span></span>
    </div>
  </div>
  <header class="masthead">
    <div class="wrap">
      <a class="brand" href="index.html">
        <img class="brand-logo" src="assets/img/bookclub-logo.png" alt="Book Club IIT Kanpur logo" width="52" height="52">
        <span class="brand-text">
          <span class="brand-name">Book Club</span>
          <span class="brand-sub">IIT Kanpur</span>
        </span>
      </a>
      <nav class="nav" aria-label="Main">
        <ul id="menu">
{items}
        </ul>
        <button class="icon-btn theme-toggle" type="button" aria-label="Switch light or dark theme">{I["sun"]}{I["moon"]}</button>
        <button class="icon-btn menu-toggle" type="button" aria-label="Menu" aria-expanded="false" aria-controls="menu">{I["menu"]}</button>
      </nav>
    </div>
  </header>
"""


def footer(site, quote_key, extra_scripts=""):
    q = site["quotes"].get(quote_key) or site["quotes"]["home"]
    nav = "".join(f'<li><a href="{h}">{l}</a></li>' for h, l in NAV[:4])
    nav2 = "".join(f'<li><a href="{h}">{l}</a></li>' for h, l in NAV[4:])
    t = site["timings"]
    return f"""
  <section class="epigraph" aria-label="Quotation">
    <div class="wrap">
      <blockquote>{esc(q["text"])}<cite>— {esc(q["author"])}</cite></blockquote>
    </div>
  </section>

  <footer class="site-footer">
    <div class="wrap">
      <div class="foot-grid">
        <div>
          <div class="foot-brand"><img src="assets/img/bookclub-logo.png" alt="" width="46" height="46"><b>Book Club<br>IIT Kanpur</b></div>
          <p>{esc(site["footer_text"])}</p>
          {socials(site, "foot-social")}
        </div>
        <div>
          <h4>Explore</h4>
          <ul>{nav}</ul>
        </div>
        <div>
          <h4>The Club</h4>
          <ul>{nav2}</ul>
        </div>
        <div>
          <h4>Timings</h4>
          <ul>
            <li>Mon – Thu · {esc(t["weekdays"])}</li>
            <li>Fri – Sun · {esc(t["weekends"])}</li>
            <li>{nowrap_room(t["location"])}</li>
          </ul>
        </div>
      </div>
      <div class="foot-base">
        <span>© <span data-year>{datetime.date.today().year}</span> Book Club IIT Kanpur</span>
      </div>
    </div>
  </footer>
  <script src="assets/js/main.js" defer></script>{extra_scripts}
</body>
</html>
"""


def page(site, fname, title, desc, active, quote, body, extra_scripts=""):
    doc = (head(title, desc) + "\n" + header(site, active) + '\n  <main id="main">\n' + body +
           "\n  </main>\n" + footer(site, quote, extra_scripts))
    with open(os.path.join(OUT, fname), "w", encoding="utf-8") as fh:
        fh.write(doc)


def timings_card(site):
    t = site["timings"]
    return f"""<div class="card index-card">
            <span class="stamp">Open 7 days</span>
            <h3>{I["clock"].replace('<svg', '<svg width="20" height="20" style="color:var(--gold)"')} Club Timings</h3>
            <p class="note">During the semester</p>
            <ul class="timings">
              <li><span>Weekdays (Mon – Thu)</span><strong>{esc(t["weekdays"])}</strong></li>
              <li><span>Weekends (Fri – Sun)</span><strong>{esc(t["weekends"])}</strong></li>
            </ul>
            <p class="note">{nowrap_room(t["location"])}</p>
          </div>"""


def socials_card(site):
    return f"""<div class="card">
            <h3>Our Socials</h3>
            <p class="muted" style="font-size:1.05rem">Club news, events and reading sessions.</p>
            {socials(site)}
          </div>"""


# ------------------------------------------------------------------ blogs
def load_blogs():
    folder = os.path.join(CONTENT, "blogs")
    posts = []
    for fname in sorted(os.listdir(folder)):
        if not fname.endswith(".md"):
            continue
        raw = open(os.path.join(folder, fname), encoding="utf-8").read()
        m = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", raw, re.S)
        if not m:
            warnings.append(f"{fname}: missing front matter, skipped")
            continue
        meta = yaml.safe_load(m.group(1)) or {}
        if meta.get("draft"):
            continue
        d = meta.get("date")
        if isinstance(d, datetime.datetime):
            d = d.date()
        if isinstance(d, str):
            try:
                d = datetime.date.fromisoformat(d[:10])
            except ValueError:
                d = None
        if not isinstance(d, datetime.date):
            warnings.append(f"{fname}: no valid date, using today")
            d = datetime.date.today()
        stem = os.path.splitext(fname)[0]
        page_name = (meta.get("page") or "").strip() or f"{stem}.html"
        if not page_name.endswith(".html"):
            page_name += ".html"
        if page_name in RESERVED:
            page_name = f"blog-{stem}.html"
        title = meta.get("title") or meta.get("book_title") or stem
        book_title = meta.get("book_title") or title
        cover = asset_path(meta.get("cover"))
        if not asset_exists(cover):
            if cover:
                warnings.append(f"{fname}: cover image '{cover}' not found")
            cover = "assets/img/bookclub-logo.png"
        paras = markdown(m.group(2), pull_quotes=True)
        first = next((p for p in paras if p.startswith("<p>")), "")
        txt = html.unescape(re.sub(r"<[^>]+>", "", first))
        posts.append({
            "file": page_name, "title": book_title, "heading": title,
            "book_author": meta.get("book_author") or "", "by": meta.get("reviewer") or "Book Club",
            "date": d, "date_label": d.strftime("%B %Y"), "mins": meta.get("read_minutes") or 3,
            "img": cover, "paras": paras,
            "excerpt": (txt[:220].rsplit(" ", 1)[0] + "…") if len(txt) > 220 else txt,
        })
    posts.sort(key=lambda p: p["date"], reverse=True)
    seen = set()
    for p in posts:
        if p["file"] in seen:
            warnings.append(f"two posts use the page name {p['file']}")
        seen.add(p["file"])
    return posts


def card_post(b):
    by = f"{esc(b['book_author'])} — reviewed by {esc(b['by'])}" if b["book_author"] else f"Reviewed by {esc(b['by'])}"
    return f"""<a class="post-card reveal" href="{esc(b['file'])}">
          <div class="post-cover"><img src="{esc(b['img'])}" alt="Cover of {esc(b['title'])}" loading="lazy" width="420" height="630"></div>
          <span class="post-meta">{b['date_label']} · {b['mins']} min read</span>
          <h3>{esc(b['title'])}</h3>
          <span class="by">{by}</span>
        </a>"""


def build_blogs(site, posts):
    if posts:
        lead = posts[0]
        cards = "\n        ".join(card_post(b) for b in posts[1:])
        lead_html = f"""<a class="lead-post reveal" href="{esc(lead['file'])}">
        <div class="post-cover"><img src="{esc(lead['img'])}" alt="Cover of {esc(lead['title'])}" width="420" height="630"></div>
        <div>
          <span class="eyebrow">Latest review</span>
          <span class="post-meta" style="display:block">{lead['date_label']} · {lead['mins']} min read</span>
          <h2>{esc(lead['heading'])}</h2>
          <p class="excerpt">{esc(lead['excerpt'])}</p>
          <span class="link-arrow">Read the review {I["arrow"]}</span>
        </div>
      </a>"""
    else:
        cards, lead_html = "", '<p class="center muted">New reviews are on their way.</p>'
    body = f"""    <header class="page-head wrap">
      <span class="eyebrow">From the reading room</span>
      <h1>Book Reviews &amp; Blogs</h1>
      <p>Reflections, Stories and more from Book Club IIT Kanpur.</p>
    </header>

    <section class="wrap" style="padding-bottom:clamp(56px,8vw,96px)">
      {lead_html}
      <div class="posts">
        {cards}
      </div>
    </section>
"""
    page(site, "blogs.html", "Blogs - Book Club IIT Kanpur", "Book reviews, reflections and stories from Book Club IIT Kanpur.",
         "blogs.html", "blogs", body)

    for i, b in enumerate(posts):
        newer = posts[i - 1] if i > 0 else None
        older = posts[i + 1] if i + 1 < len(posts) else None
        pager = '<nav class="pager" aria-label="More reviews">'
        if older:
            pager += f'<a class="prev" href="{esc(older["file"])}"><small>← Previous review</small><h4>{esc(older["title"])}</h4></a>'
        if newer:
            pager += f'<a class="next" href="{esc(newer["file"])}"><small>Next review →</small><h4>{esc(newer["title"])}</h4></a>'
        pager += "</nav>"
        paras = "\n        ".join(b["paras"])
        body = f"""    <header class="article-head wrap">
      <div class="post-cover"><img src="{esc(b['img'])}" alt="Cover of {esc(b['title'])}" width="420" height="630"></div>
      <span class="eyebrow" style="justify-content:center">{b['date_label']} · {b['mins']} min read</span>
      <h1>{esc(b['heading'])}</h1>
      <p class="by">A review by <strong>{esc(b['by'])}</strong></p>
      <div class="fleuron" aria-hidden="true">❦</div>
    </header>

    <article class="wrap">
      <div class="article dropcap">
        {paras}
      </div>
    </article>

    <div class="wrap article-foot" style="padding-bottom:clamp(56px,8vw,96px)">
      <div class="fleuron" aria-hidden="true">❦</div>
      {pager}
      <p style="margin-top:30px"><a class="link-arrow" href="blogs.html">← Back to all blogs</a></p>
    </div>
"""
        author = f" by {b['book_author']}" if b["book_author"] else ""
        page(site, b["file"], f"{b['heading']} - Book Review | Book Club IIT Kanpur",
             f"{b['title']}{author}, reviewed by {b['by']} for Book Club IIT Kanpur.", "blogs.html", "blogs", body)


# ------------------------------------------------------------------ home
def genre_href(g):
    g = GENRE_ALIAS.get(g, g)
    if g in CATALOGUE_GENRES:
        return "catalogue.html?" + urllib.parse.urlencode({"genre": g})
    return "catalogue.html?" + urllib.parse.urlencode({"q": g})     # not a catalogue genre: search for it


def bookshelves():
    def spine(label, g, c, h, w, lean=None):
        cls = "spine lean" if lean else "spine"
        extra = f";--lean:{lean}px" if lean else ""
        return (f'<a class="{cls}" href="{genre_href(g)}" style="--c:{c};--h:{h}%;--w:{w}px{extra}" '
                f'title="Browse {label}"><span>{label}</span></a>')

    def shelf(rows, scale=1.0, lean=34):
        out = []
        for i, (label, g, c, h, w) in enumerate(rows):
            last = i == len(rows) - 1 and label == SPINES[-1][0]
            out.append(spine(label, g, c, h, round(w * scale), lean if last else None))
        return ('<div class="shelf-unit"><div class="shelf">' + "".join(out) +
                '</div><div class="shelf-plank" aria-hidden="true"></div></div>')

    return ('<div class="shelf-set lg">' + shelf(SPINES) + '</div>'
            '<div class="shelf-set sm">' + shelf(SPINES[:6], .86) + shelf(SPINES[6:], .86, 24) + '</div>')


def build_home(site, posts, editions, stats):
    h = site["home"]
    about = h.get("about") or []
    first, rest = (about[0], about[1:]) if about else ("", [])
    rest_html = "\n          ".join(f"<p>{inline_md(p)}</p>" for p in rest)
    genres = "".join(f'<li><a href="{genre_href(g)}">{esc(g)}</a></li>' for g in h.get("genres", []))
    latest = "\n        ".join(card_post(b) for b in posts[:4])
    feature = ""
    if editions:
        e = editions[0]
        blurb = e.get("home_blurb") or re.sub(r"[*_]", "", e.get("description") or "")
        cover = asset_path(e.get("cover"))
        cover_html = (f'<a class="magazine-cover" href="mellifluous.html" tabindex="-1" aria-hidden="true">'
                      f'<img src="{esc(cover)}" alt="" width="560" height="792" loading="lazy"></a>') if asset_exists(cover) else ""
        feature = f"""
    <section class="section">
      <div class="wrap">
        <div class="feature reveal">
          {cover_html}
          <div>
            <span class="eyebrow">Our annual magazine</span>
            <h2>Mellifluous, {esc(e.get("title"))}</h2>
            <p>{esc(blurb)}</p>
            <a class="btn" href="mellifluous.html">Read the magazine {I["arrow"]}</a>
          </div>
        </div>
      </div>
    </section>
"""
    reviews = f"""
    <section class="section tight">
      <div class="wrap">
        <div class="section-head">
          <div><span class="eyebrow">From the reading room</span><h2>Latest reviews</h2></div>
          <a class="link-arrow" href="blogs.html">All blogs {I["arrow"]}</a>
        </div>
        <div class="posts featured">
        {latest}
        </div>
      </div>
    </section>
""" if posts else ""
    body = f"""    <section class="hero">
      <div class="wrap hero-grid">
        <div class="hero-copy">
          <span class="eyebrow">Welcome to the SAC Book Club</span>
          <h1>Book Club <em>IIT Kanpur</em></h1>
          <p class="lede">{esc(h.get("lede"))}</p>
          <form class="hero-search" action="catalogue.html" method="get" role="search">
            {I["search"]}
            <label class="sr" for="hero-q">Search the catalogue</label>
            <input id="hero-q" type="search" name="q" placeholder="Search by title, author or genre…" autocomplete="off">
            <button class="btn" type="submit">Search</button>
          </form>
          <div class="hero-actions">
            <a href="catalogue.html">Browse all {stats['books_round']} books</a>
            <a href="request.html">Request a book</a>
            <a href="rules.html">How borrowing works</a>
          </div>
        </div>
        <div class="shelf-wrap" aria-label="Browse by genre">
          {bookshelves()}
          <p class="shelf-caption">Pull a book from the shelf to browse that genre</p>
        </div>
      </div>
    </section>

    <section class="band" style="margin-top:clamp(48px,7vw,80px)" aria-label="The club in numbers">
      <div class="wrap stats">
        <div class="stat"><b>{stats['books_round']}</b><span>books on our shelves</span></div>
        <div class="stat"><b>{stats['genres']}+</b><span>genres</span></div>
        <div class="stat"><b>7</b><span>days a week</span></div>
        <div class="stat"><b>No</b><span>membership fee</span></div>
      </div>
    </section>

    <section class="section">
      <div class="wrap with-aside">
        <div class="prose reveal">
          <span class="chapter-num">Chapter the First</span>
          <h2>About us</h2>
          <div class="dropcap">
            <p>{inline_md(first)}</p>
          </div>
          {rest_html}
          <ul class="genres-inline">{genres}</ul>
          <p class="signoff">{esc(h.get("signoff"))}</p>
        </div>
        <aside>
          {timings_card(site)}
          {socials_card(site)}
        </aside>
      </div>
    </section>
{reviews}{feature}"""
    page(site, "index.html", "Home - Book Club IIT Kanpur",
         f"The SAC Book Club of IIT Kanpur: a free collection of {stats['books_round']} books run by students. "
         "Search the catalogue, request a book, read reviews and our magazine Mellifluous.",
         "index.html", "home", body)


# ------------------------------------------------------------------ rules
ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"]


def build_rules(site, rules):
    sections = []
    fines_done = False
    for n, sec in enumerate(rules.get("sections", [])):
        items = []
        for rule in sec.get("rules", []):
            table = ""
            if not fines_done and "fine" in rule.lower() and rules.get("fines"):
                rows = "".join(f'<tr><td>{inline_md(r.get("period"))}</td><td>{inline_md(r.get("fine"))}</td></tr>'
                               for r in rules["fines"])
                table = f"""
              <table class="fine-table">
                <thead><tr><th>Overdue period</th><th>Fine</th></tr></thead>
                <tbody>{rows}</tbody>
              </table>"""
                fines_done = True
            items.append(f"<li>{inline_md(rule)}{table}</li>")
        sections.append(f"""        <div class="rules-section reveal">
          <h2><span class="num">{ROMAN[n % len(ROMAN)]}.</span> {esc(sec.get("title"))}</h2>
          <ol class="rules-list">
            {chr(10).join("            " + i for i in items).strip()}
          </ol>
        </div>""")
    note = f"""
        <div class="notice reveal">
          <strong>Please note</strong>
          {inline_md(rules["note"])}
        </div>""" if rules.get("note") else ""
    body = f"""    <header class="page-head wrap">
      <span class="eyebrow">The fine print</span>
      <h1>Rules and Guidelines</h1>
      <p>{esc(rules.get("intro"))}</p>
    </header>

    <section class="wrap with-aside" style="padding-bottom:clamp(56px,8vw,96px)">
      <div class="prose">
{chr(10).join(sections)}
{note}
      </div>
      <aside>
        {timings_card(site)}
        {socials_card(site)}
      </aside>
    </section>
"""
    page(site, "rules.html", "Rules - Book Club IIT Kanpur",
         "Membership, issue and return rules, fines and guidelines of Book Club IIT Kanpur.", "rules.html", "rules", body)


# ------------------------------------------------------------------ catalogue
def build_catalogue(site, stats):
    # Live shelf status published by the club computer (tools/shelf); must be an https:// address.
    shelf = safe_url(site.get("shelf_status_url"), "Shelf status address", web_only=True)
    if shelf and not shelf.lower().startswith("https://"):
        warnings.append("Shelf status address must start with https://")
        shelf = ""
    shelf_attr = f' data-shelf="{esc(shelf)}"' if shelf else ""
    body = f"""    <header class="page-head wrap">
      <span class="eyebrow">The card catalogue</span>
      <h1>Catalogue</h1>
      <p>Search our {stats['books_round']} books by title, author or genre. Ratings are from Goodreads. If we don’t have it, <a href="request.html">request it</a>.</p>
    </header>

    <section class="wrap" style="padding-bottom:clamp(56px,8vw,96px)">
      <form class="search-panel" id="cat-form" role="search">
        <div class="search-row">
          <div class="field search-input">
            <label for="q">Search term</label>
            {I["search"]}
            <input id="q" type="search" name="q" placeholder="e.g. Dostoevsky, Harry Potter, poetry…" autocomplete="off">
          </div>
          <div class="field">
            <label for="by">Filter by</label>
            <select id="by" name="by">
              <option value="all">Everything</option>
              <option value="title">Title</option>
              <option value="author">Author</option>
              <option value="genre">Genre</option>
            </select>
          </div>
          <div class="field">
            <label for="sort">Sort by</label>
            <select id="sort" name="sort">
              <option value="best">Best match</option>
              <option value="rating">Highest rated</option>
              <option value="title">Title, A – Z</option>
            </select>
          </div>
        </div>
        <div class="chips" id="chips" aria-label="Genres"></div>
      </form>

      <div class="results-bar">
        <p class="count" id="count" aria-live="polite">Results may take a few seconds to load.</p>
        <p class="shelf-note" id="shelf-note" hidden></p>
      </div>
      <div class="books" id="books"{shelf_attr}>
        <div class="loading" aria-hidden="true"><i></i><i></i><i></i><i></i></div>
      </div>
      <div class="more-wrap"><button class="btn ghost" id="more" type="button" hidden>Show more books</button></div>
    </section>
"""
    page(site, "catalogue.html", "Catalogue - Book Club IIT Kanpur", "Search the Book Club IIT Kanpur catalogue by title, author or genre.",
         "catalogue.html", "catalogue", body, '\n  <script src="assets/js/catalogue.js" defer></script>')


# ------------------------------------------------------------------ request
def build_request(site):
    body = f"""    <header class="page-head wrap">
      <span class="eyebrow">Can’t find it on our shelves?</span>
      <h1>Request a Book</h1>
      <p>Tell us what you’d like to read. We promise to do the best we can to procure it for you.</p>
    </header>

    <section class="wrap with-aside" style="padding-bottom:clamp(56px,8vw,96px)">
      <div class="slip reveal">
        <div class="slip-head">
          <h2>Book Request Slip</h2>
          <div class="no">Book Club<br>IIT Kanpur</div>
        </div>
        <p class="intro">If you couldn't find the book you were looking for with us, fill up the form below. We promise to do the best we can to procure it for you.</p>
        <p class="required-note"><span class="req">*</span> Required fields</p>
        {form_open(site, "Book request — Book Club website")}
          <div class="form-grid">
            <div class="field">
              <label for="userName">Your name <span class="req">*</span></label>
              <input type="text" id="userName" name="Name" autocomplete="name" required>
            </div>
            <div class="field">
              <label for="rollNo">Roll No. <span class="req">*</span></label>
              <input type="text" id="rollNo" name="Roll number" required>
            </div>
            <div class="field full">
              <label for="emailID">IITK email ID <span class="req">*</span></label>
              <input type="email" id="emailID" name="email" autocomplete="email" placeholder="username@iitk.ac.in" required>
            </div>
            <div class="field">
              <label for="bookName">Name of the book <span class="req">*</span></label>
              <input type="text" id="bookName" name="Book" required>
            </div>
            <div class="field">
              <label for="authorName">Name of the author <span class="req">*</span></label>
              <input type="text" id="authorName" name="Author" required>
            </div>
            <div class="field full">
              <label for="additional">Additional details</label>
              <textarea id="additional" name="Additional details" rows="3"></textarea>
            </div>
          </div>
          <label class="check" for="verify"><input type="checkbox" id="verify" name="Checked the catalogue" value="Yes"> Have you checked our <a href="catalogue.html">catalogue</a> for the book?</label>
          <button type="submit" class="btn">Request {I["arrow"]}</button>
          <p class="form-status" role="status" hidden></p>
        </form>
      </div>
      <aside>
        <div class="card">
          <h3>Check the shelves first</h3>
          <p class="muted" style="font-size:1.05rem">We may already have it. Search our catalogue before you send a request.</p>
          <form class="hero-search" action="catalogue.html" method="get" role="search" style="box-shadow:none">
            {I["search"]}
            <label class="sr" for="side-q">Search the catalogue</label>
            <input id="side-q" type="search" name="q" placeholder="Title or author…">
          </form>
        </div>
        {timings_card(site)}
        {socials_card(site)}
      </aside>
    </section>
"""
    page(site, "request.html", "Request a Book - Book Club IIT Kanpur", "Request a book you couldn't find in the Book Club IIT Kanpur catalogue.",
         "request.html", "request", body)


# ------------------------------------------------------------------ contact & team
def monogram(name):
    parts = name.split()
    initials = (parts[0][0] + (parts[-1][0] if len(parts) > 1 else "")).upper() if parts else "?"
    return (f'<figure class="person"><div class="portrait monogram" aria-hidden="true"><span>{esc(initials)}</span></div>'
            f'<figcaption>{esc(name)}</figcaption></figure>')


def person(entry, role=""):
    name = (entry.get("name") or "").strip()
    photo = asset_path(entry.get("photo"))
    if photo and not asset_exists(photo):
        warnings.append(f"team: photo '{photo}' for {name} not found, showing initials")
        photo = ""
    if not photo:
        return monogram(name)
    r = f"<small>{role}</small>" if role else ""
    return (f'<figure class="person"><div class="portrait"><img src="{esc(photo)}" alt="{esc(name)}" loading="lazy" '
            f'width="480" height="600"></div><figcaption>{esc(name)}{r}</figcaption></figure>')


def by_name(people):
    return sorted([p for p in people or [] if (p.get("name") or "").strip()], key=lambda p: p["name"].strip().lower())


def year_label(y):
    y = str(y or "").strip()
    m = re.match(r"^(\d{4})\s*[-–]\s*(\d{2,4})$", y)
    return f"{m.group(1)} – {m.group(2)[-2:]}" if m else y


def build_contact(site, team):
    coords = "\n          ".join(person(p, "Coordinator") for p in by_name(team.get("coordinators")))
    secs = "\n          ".join(person(p) for p in by_name(team.get("secretaries")))
    past = []
    for yr in sorted(team.get("past", []), key=lambda y: str(y.get("year")), reverse=True):
        coordinators = by_name(yr.get("coordinators"))
        if any(asset_exists(asset_path(p.get("photo"))) for p in coordinators):
            inner = '<div class="people">' + "".join(person(p) for p in coordinators) + "</div>"
        else:
            inner = '<ul class="names">' + "".join(f"<li>{esc(p['name'])}</li>" for p in coordinators) + "</ul>"
        secretaries = by_name(yr.get("secretaries"))
        toggle = (f'<details class="secs"><summary><span class="when-closed">Secretaries</span>'
                  f'<span class="when-open">Hide secretaries</span></summary>'
                  f'<div class="people many">{"".join(person(p) for p in secretaries)}</div></details>') if secretaries else ""
        past.append(f'<div class="ledger-year"><h3>{esc(year_label(yr.get("year")))}</h3><div>{inner}{toggle}</div></div>')
    past_html = "\n          ".join(past)

    body = f"""    <header class="page-head wrap">
      <span class="eyebrow">Write to us</span>
      <h1>Contact Us</h1>
      <p>Have any queries or suggestions for us? We’d love to hear from you.</p>
    </header>

    <section class="wrap with-aside">
      <div class="slip reveal">
        <div class="slip-head">
          <h2>A Note to the Club</h2>
          <div class="no">Book Club<br>IIT Kanpur</div>
        </div>
        <p class="intro">Have any queries or suggestions for us? Fill up the form below to get in touch.</p>
        <p class="required-note"><span class="req">*</span> Required fields</p>
        {form_open(site, "Query — Book Club website")}
          <div class="form-grid">
            <div class="field">
              <label for="userName">Your name <span class="req">*</span></label>
              <input type="text" id="userName" name="Name" autocomplete="name" required>
            </div>
            <div class="field">
              <label for="emailID">Email ID <span class="req">*</span></label>
              <input type="email" id="emailID" name="email" autocomplete="email" required>
            </div>
            <div class="field full">
              <label for="query">Queries and/or suggestions <span class="req">*</span></label>
              <textarea id="query" name="Message" rows="4" required></textarea>
            </div>
          </div>
          <button type="submit" class="btn">Submit {I["arrow"]}</button>
          <p class="form-status" role="status" hidden></p>
        </form>
      </div>
      <aside>
        {timings_card(site)}
        {socials_card(site)}
      </aside>
    </section>

    <section class="section" id="team">
      <div class="wrap">
        <div class="center" style="margin-bottom:28px">
          <span class="eyebrow" style="justify-content:center">The people behind the shelves</span>
          <h2>Meet the team</h2>
        </div>
        <div class="tabs" role="tablist" aria-label="Team">
          <button class="tab" role="tab" id="tab-current" aria-controls="current" aria-selected="true">Current Team</button>
          <button class="tab" role="tab" id="tab-past" aria-controls="past" aria-selected="false" tabindex="-1">Past Team</button>
        </div>

        <div id="current" role="tabpanel" aria-labelledby="tab-current">
          <div class="group-title"><h3>Coordinators</h3></div>
          <div class="people leads">
          {coords}
          </div>
          <div class="fleuron" aria-hidden="true">❦</div>
          <div class="group-title"><h3>Secretaries</h3></div>
          <div class="people">
          {secs}
          </div>
        </div>

        <div id="past" role="tabpanel" aria-labelledby="tab-past">
          <div class="group-title"><h3>Past Team</h3><p>With gratitude to those who kept the shelves before us.</p></div>
          <div class="ledger">
          {past_html}
          </div>
        </div>
      </div>
    </section>
"""
    page(site, "contact.html", "Contact Us - Book Club IIT Kanpur", "Get in touch with Book Club IIT Kanpur and meet the team.",
         "contact.html", "contact", body)


# ------------------------------------------------------------------ mellifluous
def build_mellifluous(site, editions):
    blocks = []
    for n, e in enumerate(editions):
        number = len(editions) - n
        roman = ROMAN[number - 1] if number <= len(ROMAN) else str(number)
        title = f"Mellifluous — {e.get('title')}"
        desc = "".join(markdown(e.get("description") or ""))
        url = safe_url(e.get("flipbook"), f"Mellifluous '{e.get('title', '')}' flipbook", web_only=True)
        blocks.append(f"""      <article class="edition reveal">
        <div class="edition-head">
          <span class="roman" aria-hidden="true">{roman}</span>
          <h2>{esc(title)}</h2>
          {desc}
        </div>
        <div class="flipbook">
          <iframe src="{esc(url)}" title="{esc(title)} flipbook" loading="lazy" allowfullscreen></iframe>
        </div>
        <div class="flipbook-foot"><a class="link-arrow" href="{esc(url)}" target="_blank" rel="noopener">Open full screen {I["expand"]}</a></div>
      </article>""")
    body = f"""    <header class="page-head wrap">
      <span class="eyebrow">The annual magazine of Book Club IIT Kanpur</span>
      <h1><em style="font-weight:500">Mellifluous</em></h1>
      <p>Created by and for book lovers. Turn the pages below.</p>
    </header>

    <section class="wrap" style="padding-bottom:clamp(24px,4vw,40px)">
{chr(10).join(blocks)}
    </section>
"""
    page(site, "mellifluous.html", "Mellifluous - Book Club IIT Kanpur",
         "Mellifluous, the annual magazine of Book Club IIT Kanpur, created by and for book lovers.",
         "mellifluous.html", "mellifluous", body)


def build_404(site):
    body = """    <header class="page-head wrap" style="padding-bottom:clamp(64px,10vw,120px)">
      <span class="eyebrow">Error 404</span>
      <h1>This page has been misshelved</h1>
      <p>We looked between the stacks but couldn’t find it. Try the <a href="index.html">home page</a> or search the <a href="catalogue.html">catalogue</a>.</p>
    </header>
"""
    page(site, "404.html", "Page not found - Book Club IIT Kanpur", "Page not found.", "", "catalogue", body)


# ------------------------------------------------------------------ static files & images
def has_location(path):
    try:
        with Image.open(path) as im:
            exif = im.getexif()
            return bool(exif and exif.get_ifd(0x8825))
    except Exception:
        return False


def copy_static():
    shutil.copytree(os.path.join(ROOT, "assets"), os.path.join(OUT, "assets"),
                    ignore=shutil.ignore_patterns("uploads"))
    shutil.copytree(os.path.join(ROOT, "data"), os.path.join(OUT, "data"))
    if os.path.isdir(os.path.join(ROOT, "admin")):
        shutil.copytree(os.path.join(ROOT, "admin"), os.path.join(OUT, "admin"))
    # Photos uploaded through the admin panel: re-encode without metadata and cap their size.
    uploads = os.path.join(ROOT, "assets", "uploads")
    if os.path.isdir(uploads):
        dest_dir = os.path.join(OUT, "assets", "uploads")
        os.makedirs(dest_dir, exist_ok=True)
        for f in os.listdir(uploads):
            src = os.path.join(uploads, f)
            if not os.path.isfile(src):
                continue
            dest = os.path.join(dest_dir, f)
            if f.lower().endswith(IMG_EXT) and not f.lower().endswith(".gif"):
                try:
                    with Image.open(src) as im:
                        im = ImageOps.exif_transpose(im)
                        im.thumbnail((1400, 1400))
                        fmt = {"jpg": "JPEG", "jpeg": "JPEG", "png": "PNG", "webp": "WEBP"}[f.rsplit(".", 1)[1].lower()]
                        if fmt == "JPEG" and im.mode not in ("RGB", "L"):
                            im = im.convert("RGB")
                        im.save(dest, fmt, quality=82)
                    continue
                except Exception as e:
                    warnings.append(f"could not process upload {f}: {e}")
            shutil.copy2(src, dest)


def main():
    leaks = [os.path.relpath(os.path.join(dp, f), ROOT)
             for dp, _, files in os.walk(os.path.join(ROOT, "assets"))
             for f in files if f.lower().endswith(IMG_EXT) and has_location(os.path.join(dp, f))]
    if leaks:
        print("ERROR: these images contain GPS location data. Remove them from the repository and upload a copy "
              "without location (the admin panel does this automatically):\n  " + "\n  ".join(leaks))
        sys.exit(1)

    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)

    site = load_json("site.json")
    team = load_json("team.json")
    rules = load_json("rules.json")
    editions = load_json("mellifluous.json").get("editions", [])
    posts = load_blogs()

    cat = json.load(open(os.path.join(ROOT, "data", "catalogue.json"), encoding="utf-8"))
    genres = {b["g"] for b in cat if b.get("g")}
    CATALOGUE_GENRES.update(genres)
    # The size claimed on the site is set in content/site.json (it includes magazines not in the catalogue).
    copies = sum(b.get("n", 1) for b in cat)
    claim = str(site.get("collection_size") or "").strip() or f"{copies // 1000 * 1000:,}+"
    stats = {"books_round": claim, "genres": len(genres) // 5 * 5}

    copy_static()
    build_blogs(site, posts)
    build_home(site, posts, editions, stats)
    build_rules(site, rules)
    build_catalogue(site, stats)
    build_request(site)
    build_contact(site, team)
    build_mellifluous(site, editions)
    build_404(site)
    open(os.path.join(OUT, ".nojekyll"), "w").close()

    pages = len([f for f in os.listdir(OUT) if f.endswith(".html")])
    print(f"Built {pages} pages into {os.path.relpath(OUT, ROOT)}/ ({len(posts)} blog posts).")
    for w in warnings:
        print("warning:", w)


if __name__ == "__main__":
    main()
