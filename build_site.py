#!/usr/bin/env python3
"""
build_site.py — Faithful static mirror of https://cardealers.gtacfinance.com/

Strategy (WordPress + Elementor site):
  1. BFS-crawl every same-host HTML page starting from the homepage.
  2. Download every referenced asset (CSS/JS/images incl. all srcset variants,
     fonts, and url() refs inside CSS), dedupe by md5 content hash.
  3. Post-process HTML: de-lazy images/backgrounds, rewrite all absolute
     site URLs -> local relative paths, keep external form embeds verbatim.
  4. Emit a GitHub-Pages-ready tree under site/ with pretty-URL folders.

Run stages individually:  python3 build_site.py crawl | assets | build | all
"""
import os, re, sys, json, hashlib, time
from urllib.parse import urljoin, urlparse, urldefrag, unquote
import urllib.request

BASE = "https://cardealers.gtacfinance.com/"
HOST = "cardealers.gtacfinance.com"
DASHBOARD_URL = "https://app.greenlightrecover.com/login"  # MY ACCOUNT / Dealer Login target
# dark gradient baked over background images so overlaid text stays readable
SCRIM_GRAD = "linear-gradient(rgba(7,21,23,.42),rgba(7,21,23,.56))"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

ROOT = os.path.dirname(os.path.abspath(__file__))
RAW  = os.path.join(ROOT, "raw")      # raw downloaded HTML per page
SITE = os.path.join(ROOT, "docs")     # final static output (GitHub Pages serves /docs)
ASSETS_SUB = "assets"                 # asset dir inside site/
for d in (RAW, SITE): os.makedirs(d, exist_ok=True)

# ---------------------------------------------------------------- helpers
def fetch(url, binary=False, tries=3):
    req = urllib.request.Request(url, headers={"User-Agent": UA,
        "Accept": "*/*", "Accept-Language": "en-US,en;q=0.9"})
    last = None
    for i in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                data = r.read()
                ctype = r.headers.get("Content-Type", "")
                final = r.geturl()
                return (data if binary else data.decode("utf-8", "replace")), ctype, final
        except Exception as e:
            last = e; time.sleep(1.5 * (i + 1))
    print(f"   !! FAILED {url}: {last}")
    return (None, None, url)

def canon(slug):
    """Canonicalize case-variant slugs (WP slugs are case-insensitive).
    /BOOK-A-CALL/ and /book-a-call/ are the same post (canonical = lowercase);
    a case-insensitive local FS can't hold both folders anyway."""
    return slug.lower() if slug.lower() == "book-a-call" else slug

def slug_for(url):
    """Map a page URL to an output dir (pretty URLs)."""
    p = urlparse(url).path
    if p in ("", "/"): return ""       # homepage -> site/index.html
    return canon(p.strip("/"))          # e.g. faq -> site/faq/index.html

def raw_path(url):
    s = slug_for(url)
    name = "index" if s == "" else s.replace("/", "__")
    return os.path.join(RAW, name + ".html")

# ---------------------------------------------------------------- crawl
SKIP_EXT = (".pdf,.jpg,.jpeg,.png,.gif,.svg,.webp,.zip,.mp4,.webm,.css,.js,"
            ".ico,.woff,.woff2,.ttf,.eot").split(",")

def is_page_link(href):
    if not href: return False
    href = href.strip()
    if href.startswith(("#", "mailto:", "tel:", "javascript:", "data:")): return False
    u = urljoin(BASE, href)
    pr = urlparse(u)
    if pr.netloc != HOST: return False
    path = pr.path.lower()
    if any(path.endswith(e) for e in SKIP_EXT): return False
    if "/wp-content/" in path or "/wp-json/" in path or "/wp-admin/" in path: return False
    return True

def crawl():
    from bs4 import BeautifulSoup
    seen, queue, pages = set(), [BASE], {}
    while queue:
        url = queue.pop(0)
        key = urldefrag(url)[0].rstrip("/") or BASE
        if key in seen: continue
        seen.add(key)
        print(f" -> {url}")
        html, ctype, final = fetch(url)
        if html is None or "text/html" not in (ctype or ""):
            continue
        pages[url] = raw_path(url)
        with open(raw_path(url), "w", encoding="utf-8") as f:
            f.write(html)
        soup = BeautifulSoup(html, "html.parser")
        for a in soup.find_all("a", href=True):
            h = a["href"]
            if is_page_link(h):
                u = urldefrag(urljoin(BASE, h))[0]
                if (u.rstrip("/") or BASE) not in seen:
                    queue.append(u)
    with open(os.path.join(ROOT, "pages.json"), "w") as f:
        json.dump({u: os.path.basename(p) for u, p in pages.items()}, f, indent=2)
    print(f"\nCrawled {len(pages)} pages.")

# ---------------------------------------------------------------- asset mapping
def clean(url):
    return urldefrag(urljoin(BASE, url))[0]        # drop #fragment (not sent)

def local_for(url):
    """Local path (relative to site root) for a downloadable asset, else None (leave external)."""
    u = urljoin(BASE, url)
    pr = urlparse(u)
    if pr.netloc == HOST:
        path = unquote(pr.path).lstrip("/")
        return (ASSETS_SUB + "/" + path) if path else None
    if pr.netloc == "fonts.googleapis.com":
        fam = re.search(r"family=([^&:]+)", pr.query)
        name = re.sub(r"[^A-Za-z0-9]", "", (fam.group(1) if fam else "gfont"))
        h = hashlib.md5((pr.query or pr.path).encode()).hexdigest()[:8]
        return f"{ASSETS_SUB}/fonts/{name}-{h}.css"
    if pr.netloc in ("fonts.gstatic.com", "use.fontawesome.com"):
        return f"{ASSETS_SUB}/fonts/{pr.netloc}/" + unquote(pr.path).lstrip("/")
    return None

# page-slug lookup built during build()
PAGE_SLUGS = {}   # normalized path key -> slug

def page_slug_for(url):
    pr = urlparse(urljoin(BASE, url))
    if pr.netloc != HOST: return None
    key = pr.path.strip("/")
    return PAGE_SLUGS.get(key)

def rel(target_root_path, page_slug):
    start = page_slug if page_slug else "."
    return os.path.relpath(target_root_path, start).replace(os.sep, "/")

def page_link(target_url, page_slug):
    s = page_slug_for(target_url)
    if s is None: return None
    dest = rel(s if s else ".", page_slug)
    return "./" if dest == "." else (dest.rstrip("/") + "/")

# ---------------------------------------------------------------- downloading
DOWNLOADED = {}   # abs-url -> local root path
MD5 = {}          # md5 -> first local path (duplicate reporting)
LAZY_BG = re.compile(r"""url\(\s*(['"]?)[^)'"]*#\}([^)'"]+)\1\s*\)""")
CSS_URL = re.compile(r"""url\(\s*(['"]?)([^)'"]+)\1\s*\)""")

def download(url):
    u = clean(url)
    if u in DOWNLOADED: return DOWNLOADED[u]
    lp = local_for(u)
    if lp is None: return None
    is_css = lp.endswith(".css")
    data, ctype, _ = fetch(u, binary=not is_css)
    if data is None: return None
    dest = os.path.join(SITE, lp)
    if os.path.exists(dest) and os.path.getsize(dest) > 0:   # disk cache: skip re-download
        DOWNLOADED[u] = lp
        return lp
    DOWNLOADED[u] = lp
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    if is_css:
        css = rewrite_css(data, u, lp)
        with open(dest, "w", encoding="utf-8") as f: f.write(css)
    else:
        with open(dest, "wb") as f: f.write(data)
        m = hashlib.md5(data).hexdigest()
        MD5.setdefault(m, []).append(lp)
    return lp

def rewrite_css(text, css_url, css_local):
    text = LAZY_BG.sub(lambda m: f'url("{m.group(2)}")', text)   # de-lazy bg in css
    css_dir = os.path.dirname(css_local)
    def repl(m):
        raw = m.group(2).strip()
        if raw.startswith(("data:", "#")): return m.group(0)
        child = download(urljoin(css_url, raw))
        if not child: return m.group(0)
        return f'url("{os.path.relpath(child, css_dir).replace(os.sep, "/")}")'
    return CSS_URL.sub(repl, text)

# ---------------------------------------------------------------- build pages
def asset_link(url, slug):
    """Download a same-host/font asset and return its relative link, else the cleaned original."""
    lp = download(url)
    if lp: return rel(lp, slug)
    return clean(url)

def rewrite_srcset(val, base_url, slug):
    out = []
    for part in val.split(","):
        part = part.strip()
        if not part: continue
        bits = part.split()
        u = urljoin(base_url, bits[0])
        link = asset_link(u, slug) if local_for(u) else clean(bits[0])
        out.append(" ".join([link] + bits[1:]))
    return ", ".join(out)

# Menu links to remove from the whole site (header + footer), per request.
REMOVE_LINK_HOSTS = ("gtacfinance.com", "gtacfoundation.org")

def strip_removed_menu_links(soup):
    """Remove GTAC FINANCE / GTAC FOUNDATION menu items site-wide. In the header the
    'GTAC' dropdown then holds only 'Contact Us' -> collapse it into a direct
    top-level 'Contact Us' link. In the footer their column is left empty -> remove
    the empty nav widget and its orphaned 'GTAC' heading."""
    # 1) remove the two external org links (their <li> menu items)
    for a in list(soup.find_all("a", href=True)):
        host = urlparse(a["href"]).netloc.lower()
        if host.startswith("www."): host = host[4:]
        if host in REMOVE_LINK_HOSTS:
            (a.find_parent("li") or a).decompose()
    # 2) header: collapse the single-item 'GTAC' dropdown into a plain 'Contact Us' link
    for pa in list(soup.find_all("a", href="#")):
        if pa.get_text(" ", strip=True) != "GTAC":
            continue
        li = pa.find_parent("li")
        sub = li.find("ul") if li else None
        child = sub.find("a", href=True) if sub else None
        if not child:
            continue
        new_href, new_txt = child["href"], child.get_text(" ", strip=True)
        for sp in pa.find_all("span"):     # drop the dropdown toggle/arrow
            sp.decompose()
        pa.clear(); pa.append(new_txt)
        pa["href"] = new_href
        pa["aria-expanded"] = "false"
        for attr in ("aria-haspopup",):
            if pa.has_attr(attr): del pa[attr]
        sub.decompose()
        if li and li.get("class"):
            li["class"] = [c for c in li["class"] if c != "menu-item-has-children"]
    # 3) footer: drop nav-menu widgets left empty + the orphaned 'GTAC' heading
    for ul in list(soup.select("ul.elementor-nav-menu")):
        if not ul.find("li"):
            (ul.find_parent(class_="elementor-widget-nav-menu") or ul).decompose()
    for h in list(soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])):
        if h.get_text(" ", strip=True) == "GTAC":
            (h.find_parent(class_="elementor-widget-heading") or h).decompose()

# White text on the brand teal (#03b0a6) is only ~2.6:1 contrast. Deepen the teal
# ONLY where it is a *background* so white text reads clearly; teal text/accents stay.
TEAL_SRC = "#03b0a6"
TEAL_BG_DEEP = "#017d73"
def deepen_teal_backgrounds():
    pat = re.compile(r"(background(?:-color)?\s*:\s*)#03b0a6", re.I)
    for f in glob_css():
        txt = open(f, encoding="utf-8", errors="ignore").read()
        new = pat.sub(lambda m: m.group(1) + TEAL_BG_DEEP, txt)
        if new != txt:
            open(f, "w", encoding="utf-8").write(new)
            print("deepened teal backgrounds in", os.path.basename(f))

def glob_css():
    import glob
    return glob.glob(os.path.join(SITE, ASSETS_SUB, "wp-content", "cache",
                                  "tw_optimize", "css", "*.css"))

def build():
    from bs4 import BeautifulSoup
    pages = json.load(open(os.path.join(ROOT, "pages.json")))
    # copy the polish layer into the output tree
    src = os.path.join(ROOT, "assets-src", "redesign.css")
    if os.path.exists(src):
        dst = os.path.join(SITE, ASSETS_SUB, "redesign.css")
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(src, encoding="utf-8") as a, open(dst, "w", encoding="utf-8") as b:
            b.write(a.read())
        print("copied redesign.css")
    # build slug lookup
    for url in pages:
        s = slug_for(url)
        PAGE_SLUGS[urlparse(url).path.strip("/")] = s
    print(f"Building {len(pages)} pages ...")
    for url in pages:
        slug = slug_for(url)
        html = open(os.path.join(RAW, pages[url]), encoding="utf-8").read()
        soup = BeautifulSoup(html, "html.parser")
        strip_removed_menu_links(soup)

        # de-lazy images -> promote real url into src/srcset, switch to native lazy-loading
        for img in soup.find_all("img"):
            was_lazy = img.get("data-src") or (img.get("class") and "lazy" in img.get("class"))
            if img.get("data-src"):
                img["src"] = img["data-src"]; del img["data-src"]
            if img.get("data-srcset"):
                img["srcset"] = img["data-srcset"]; del img["data-srcset"]
            cls = img.get("class")
            if cls and "lazy" in cls:
                img["class"] = [c for c in cls if c != "lazy"]
            if was_lazy and not img.get("loading"):
                img["loading"] = "lazy"

        # Elementor lazy-loads container background images (background-image:none
        # !important until its JS adds .e-lazyloaded). That JS is deferred, so mark
        # every container e-no-lazyload -> backgrounds render immediately, no JS needed.
        for con in soup.select(".e-con"):
            cls = con.get("class", [])
            if "e-no-lazyload" not in cls:
                con["class"] = cls + ["e-no-lazyload"]

        # de-lazy iframes (JotForm / Replit calculators / Google Maps embeds) so the
        # real external src loads without depending on the deferred lazyload JS
        for ifr in soup.find_all("iframe"):
            if ifr.get("data-src"):
                ifr["src"] = ifr["data-src"]; del ifr["data-src"]
            cls = ifr.get("class")
            if cls and "lazy" in cls:
                ifr["class"] = [c for c in cls if c != "lazy"]
            if not ifr.get("loading"):
                ifr["loading"] = "lazy"

        # <link> stylesheets / icons / preload
        for l in soup.find_all("link", href=True):
            rels = " ".join(l.get("rel", [])).lower()
            if any(k in rels for k in ("stylesheet", "icon", "preload", "apple-touch")):
                if local_for(l["href"]):
                    l["href"] = asset_link(l["href"], slug)

        # <script src>
        for s in soup.find_all("script", src=True):
            if local_for(s["src"]):
                s["src"] = asset_link(s["src"], slug)

        # tw_optimize deferred scripts (loaded on interaction) -> localize host ones
        for s in soup.find_all(attrs={"data-two_delay_src": True}):
            v = s["data-two_delay_src"]
            if v and v.startswith("http") and local_for(v):
                s["data-two_delay_src"] = asset_link(v, slug)

        # <img>/<source> src + srcset, <video poster>
        for tag in soup.find_all(["img", "source"]):
            if tag.get("src") and local_for(tag["src"]):
                tag["src"] = asset_link(tag["src"], slug)
            if tag.get("srcset"):
                tag["srcset"] = rewrite_srcset(tag["srcset"], url, slug)
        for v in soup.find_all("video"):
            if v.get("poster") and local_for(v["poster"]):
                v["poster"] = asset_link(v["poster"], slug)

        # <a href> — internal pages -> relative page links; internal assets -> asset;
        #            everything external (jotform/replit/maps/social/…) left verbatim
        for a in soup.find_all("a", href=True):
            h = a["href"].strip()
            if h.startswith(("#", "mailto:", "tel:", "javascript:", "data:")): continue
            # Account/login entry points (MY ACCOUNT button, Dealer Login) -> live dashboard.
            # The static dealer-login/reset pages have no backend to authenticate against.
            if page_slug_for(h) in ("dealer-login", "dealer-password-reset"):
                a["href"] = DASHBOARD_URL
                continue
            pl = page_link(h, slug)
            if pl is not None:
                a["href"] = pl
            elif local_for(h):
                a["href"] = asset_link(h, slug)

        # inline style="" : de-lazy backgrounds (url(data:..#}REAL) -> url(REAL)) then localize
        for tag in soup.find_all(style=True):
            st = LAZY_BG.sub(lambda m: f'url("{m.group(2)}")', tag["style"])
            def repl(m, base=url, sl=slug):
                raw = m.group(2).strip()
                if raw.startswith(("data:", "#")): return m.group(0)
                u = urljoin(base, raw)
                if not local_for(u): return m.group(0)
                return f'url("{asset_link(u, sl)}")'
            st = CSS_URL.sub(repl, st)
            # bake a readability scrim INTO real background images (guarantees text
            # contrast regardless of DOM nesting — more robust than a ::before overlay)
            st = re.sub(r"(background\s*:\s*)(url\((?![\"']?data:))",
                        r"\1" + SCRIM_GRAD + r", \2", st, flags=re.I)
            tag["style"] = st

        # <style> blocks : same de-lazy + localize
        for st in soup.find_all("style"):
            if st.string:
                txt = LAZY_BG.sub(lambda m: f'url("{m.group(2)}")', st.string)
                def repl2(m, base=url, sl=slug):
                    raw = m.group(2).strip()
                    if raw.startswith(("data:", "#")): return m.group(0)
                    u = urljoin(base, raw)
                    if not local_for(u): return m.group(0)
                    return f'url("{asset_link(u, sl)}")'
                st.string.replace_with(CSS_URL.sub(repl2, txt))

        # Ensure Elementor entrance-animation content is visible without relying on
        # deferred JS (tw_optimize delays the animation JS until user interaction),
        # then load the professional polish layer LAST so it wins the cascade.
        if soup.head:
            fix = soup.new_tag("style")
            fix.string = (".elementor-invisible{opacity:1 !important;visibility:visible !important;}"
                          ".elementor-widget.elementor-invisible{opacity:1 !important;}")
            soup.head.append(fix)
            link = soup.new_tag("link", rel="stylesheet")
            link["href"] = rel(ASSETS_SUB + "/redesign.css", slug)
            soup.head.append(link)

        out_dir = os.path.join(SITE, slug)
        os.makedirs(out_dir, exist_ok=True)
        with open(os.path.join(out_dir, "index.html"), "w", encoding="utf-8") as f:
            f.write(str(soup))
        print(f"   [{slug or '/'}] ok")

    # accessibility: deepen teal backgrounds for readable white text
    deepen_teal_backgrounds()

    # report
    dups = {m: v for m, v in MD5.items() if len(set(v)) > 1}
    manifest = {"pages": len(pages), "assets_downloaded": len(DOWNLOADED),
                "duplicate_md5_groups": len(dups),
                "duplicates": {m: sorted(set(v)) for m, v in dups.items()}}
    json.dump(manifest, open(os.path.join(ROOT, "manifest.json"), "w"), indent=2)
    print(f"\nAssets downloaded: {len(DOWNLOADED)} | real duplicate-content groups: {len(dups)}")

if __name__ == "__main__":
    stage = sys.argv[1] if len(sys.argv) > 1 else "all"
    if stage in ("crawl", "all"):
        print("== CRAWL =="); crawl()
    if stage in ("build", "all"):
        print("== BUILD =="); build()
