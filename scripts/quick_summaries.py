"""Produce brief, source-grounded extracts for the static news app.

No generative API or paywall bypass: uses publisher-provided previews and
publicly accessible article paragraphs. Does not invent missing key points.
"""
import concurrent.futures
import datetime as dt
import hashlib
import html
import re
import sys
import urllib.parse
import urllib.request

from bs4 import BeautifulSoup

UA = "Mozilla/5.0 (compatible; TheCommercialBrief/1.2; news research)"
BLOCKED = ("news.google.com", "google.com", "bing.com")
UNHELPFUL = ("subscribe", "sign up", "cookie policy", "newsletter",
             "advertisement", "all rights reserved", "privacy policy",
             "accept cookies", "read more", "follow us", "share this")
SENTENCES = re.compile(r'(?<=[.!?])\s+(?=[A-Z0-9"“‘])')


def compact(text):
    return re.sub(r"(?<=[a-z0-9])\.(?=[A-Z])", ". ", re.sub(r"\s+", " ", html.unescape(text or ""))).strip()


def sentence_candidates(raw):
    pieces = SENTENCES.split(compact(raw))
    out = []
    seen = set()
    for part in pieces:
        part = part.strip(" -•\t\n")
        if not 45 <= len(part) <= 550:
            continue
        if any(word in part.casefold() for word in UNHELPFUL):
            continue
        fingerprint = re.sub(r"[^a-z0-9]", "", part.casefold())[:95]
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        out.append(part)
    return out


def shorten(sentence, words=42):
    parts = sentence.split()
    return " ".join(parts[:words]) + ("…" if len(parts) > words else "")


def build_summary(raw, origin="publisher preview"):
    sentences = sentence_candidates(raw)
    if not sentences:
        return {}
    lead = shorten(sentences[0], 50)
    if len(lead) < 65:
        return {}
    points = [shorten(p, 33) for p in sentences[1:4] if len(p) > 55]
    return {"summary": lead, "key_points": points,
            "summary_origin": origin}


def read_public_article(url):
    try:
        u = urllib.parse.urlparse(url)
        if u.scheme != "https" or not u.hostname:
            return ""
        host = u.hostname.lower()
        if host in BLOCKED or host.endswith(".google.com"):
            return ""
        req = urllib.request.Request(url, headers={"User-Agent": UA,
                    "Accept": "text/html,application/xhtml+xml"})
        with urllib.request.urlopen(req, timeout=8) as reply:
            finalhost = (urllib.parse.urlparse(reply.geturl()).hostname or "").lower()
            if finalhost in BLOCKED or finalhost.endswith(".google.com"):
                return ""
            if "html" not in (reply.headers.get("Content-Type", "").lower()):
                return ""
            raw = reply.read(850_000)
        soup = BeautifulSoup(raw, "html.parser")
        for node in soup.select("script, style, nav, header, footer, aside, form, noscript, button"):
            node.decompose()
        body = (soup.select_one("[itemprop='articleBody']") or
                soup.select_one(".field--name-body") or
                soup.select_one(".article-content") or
                soup.select_one(".article__body") or
                soup.select_one("article") or
                soup.select_one("main"))
        if body is None:
            return ""
        paragraphs = []
        for node in body.find_all("p"):
            text = compact(node.get_text(" ", strip=True))
            if 65 <= len(text) <= 1400 and not any(
                term in text.casefold() for term in UNHELPFUL
            ):
                paragraphs.append(text)
        if len(paragraphs) < 3:
            # Publisher-provided metadata is useful when the article body is
            # rendered client-side or not publicly available.
            for attrs in ({"property":"og:description"}, {"name":"description"}):
                meta=soup.find("meta",attrs=attrs)
                candidate=compact(meta.get("content","") if meta else "")
                if len(candidate)>=100:
                    return candidate
            return ""
        return " ".join(paragraphs[:10])[:6500]
    except Exception as exc:
        print("Article unavailable:", str(exc)[:100], file=sys.stderr)
        return ""


def enrich_summaries(articles, previous):
    older = {a.get("id"): a for a in previous if a.get("summary")}
    def one(item):
        a = dict(item)
        cached = older.get(a.get("id"))
        if cached:
            for field in ("summary", "key_points", "summary_origin"):
                if field in cached:
                    a[field] = cached[field]
            a.pop("preview", None)
            return a
        preview = compact(a.pop("preview", ""))
        headline = compact(a.get("title", "")).casefold()
        # Many Google News feed descriptions repeat only the headline and source.
        if preview.casefold().startswith(headline) and len(preview) < len(headline) + 75:
            preview = ""
        url = a.get("url", "")
        content = read_public_article(url) if a.get("direct_source") else ""
        result = build_summary(content, "public article text") if content else {}
        if not result and preview and len(preview) >= 110:
            result = build_summary(preview, "publisher preview")
        a.update(result)
        a.pop("direct_source", None)
        return a

    # Only direct publisher links are opened; Google redirect/publisher blocks
    # do not cause missing text to be invented.
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        return list(pool.map(one, articles))


def fpa_feature_stories():
    """Read dated, freely discoverable FP&A Trends article listings."""
    url = "https://fpa-trends.com/fpa-articles"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=18) as response:
            soup = BeautifulSoup(response.read(1_200_000), "html.parser")
        out = []
        seen = set()
        pattern = re.compile(
            r"\b(\d{1,2}\s+(?:January|February|March|April|May|June|July|"
            r"August|September|October|November|December)\s+20\d{2})\b",
            re.I
        )
        for anchor in soup.find_all("a", href=True):
            href = urllib.parse.urljoin(url, anchor["href"])
            parsed = urllib.parse.urlparse(href)
            if parsed.hostname != "fpa-trends.com" or not parsed.path.startswith("/article/"):
                continue
            title = compact(anchor.get_text(" ", strip=True))
            if not (19 <= len(title) <= 190) or title.lower() in ("read more", "continue reading"):
                continue
            if href in seen:
                continue
            match = None
            for parent in list(anchor.parents)[:7]:
                context = compact(parent.get_text(" ", strip=True))
                if len(context) > 3800:
                    break
                match = pattern.search(context)
                if match:
                    break
            if not match:
                continue
            try:
                published = dt.datetime.strptime(match.group(1), "%d %B %Y").replace(tzinfo=dt.timezone.utc)
            except ValueError:
                continue
            now = dt.datetime.now(dt.timezone.utc)
            if not dt.timedelta(0) <= now-published <= dt.timedelta(days=31):
                continue
            seen.add(href)
            ident = hashlib.sha1((title.casefold()+"fpa trends").encode()).hexdigest()[:16]
            out.append({"id": ident, "title": title, "description": "",
                        "url": href, "source": "FP&A Trends", "region": "Global",
                        "section": "commercial-finance", "published": published.isoformat(),
                        "direct_source": True})
            if len(out)>=12:
                break
        print("FP&A Trends featured articles", len(out))
        return out
    except Exception as exc:
        print("FP&A Trends articles unavailable:",str(exc)[:160],file=sys.stderr)
        return []


def ahdb_market_stories():
    """Official UK livestock, dairy, cereals and supply outlook news."""
    url="https://ahdb.org.uk/Query/30?title=Latest+news+stories"
    try:
        req=urllib.request.Request(url,headers={"User-Agent":UA})
        with urllib.request.urlopen(req,timeout=18) as response:
            soup=BeautifulSoup(response.read(1_100_000),"html.parser")
        now=dt.datetime.now(dt.timezone.utc)
        pattern=re.compile(
            r"^(\d{1,2}\s+(?:January|February|March|April|May|June|July|"
            r"August|September|October|November|December)\s+20\d{2})\s+",
            re.I
        )
        out=[]
        seen=set()
        for link in soup.find_all("a",href=True):
            text=compact(link.get_text(" ",strip=True))
            match=pattern.match(text)
            if not match:
                continue
            href=urllib.parse.urljoin(url,link["href"])
            if urllib.parse.urlparse(href).hostname not in ("ahdb.org.uk","www.ahdb.org.uk"):
                continue
            if href in seen:
                continue
            published=dt.datetime.strptime(match.group(1),"%d %B %Y").replace(tzinfo=dt.timezone.utc)
            if not dt.timedelta(0) <= now-published <= dt.timedelta(days=30):
                continue
            heading=link.find(["h2","h3","h4","h5"])
            desc_node=link.find("p")
            tail=compact(text[match.end():])
            description=compact(desc_node.get_text(" ",strip=True)) if desc_node else ""
            title=compact(heading.get_text(" ",strip=True)) if heading else ""
            if not title and description and tail.endswith(description):
                title=compact(tail[:-len(description)])
            if not title:
                title=tail[:150].rsplit(" ",1)[0]
            if len(title)<20:
                continue
            seen.add(href)
            ident=hashlib.sha1((title.casefold()+"ahdb").encode()).hexdigest()[:16]
            out.append({"id":ident,"title":title,"description":description[:260],
                        "preview":description[:1200],"url":href,"source":"AHDB",
                        "region":"UK","section":"commodities","published":published.isoformat(),
                        "direct_source":True})
            if len(out)>=15:
                break
        print("AHDB food-sector market stories",len(out))
        return out
    except Exception as exc:
        print("AHDB news unavailable:",str(exc)[:160],file=sys.stderr)
        return []
