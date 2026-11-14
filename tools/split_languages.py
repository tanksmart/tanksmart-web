#!/usr/bin/env python3
"""Make one page per language from the multilingual pages.

The multilingual pages in the repo root (blog.html, guides.html, the guides,
about.html, privacy.html) stay the source that people and the weekly routine
edit. This script writes /<lang>/<page>.html with only that language in it,
plus hreflang links, _redirects and the sitemap. Netlify runs it on every
deploy (netlify.toml), so the language pages always match the sources.
Standard library only.
"""
import html
import os
import re
import sys
from datetime import date

SITE = 'https://tanksmart.eu'
LANGS = ['en', 'sl', 'hr', 'de', 'es', 'it', 'cs', 'uk']
DEFAULT = 'en'
# browser languages that should land on each version (Netlify Language= condition)
BROWSER = {'sl': 'sl', 'hr': 'hr,sr,bs', 'de': 'de', 'es': 'es', 'it': 'it', 'cs': 'cs,sk', 'uk': 'uk'}
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INIT = "setLang((['en','sl','hr','de','es','it','cs','uk'].indexOf(urlLang) !== -1) ? urlLang : 'en');"


def read(p):
    with open(os.path.join(ROOT, p), encoding='utf-8') as f:
        return f.read()


def write(p, s):
    full = os.path.join(ROOT, p)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, 'w', encoding='utf-8') as f:
        f.write(s)


def source_pages():
    out = []
    for f in sorted(os.listdir(ROOT)):
        if f.endswith('.html') and f != 'index.html':
            s = read(f)
            if all('id="section-%s"' % l in s for l in LANGS) and INIT in s:
                out.append(f)
    return out


def div_end(s, start):
    """Index just after the </div> that closes the <div at start."""
    depth = 0
    for m in re.finditer(r'<div\b|</div>', s[start:]):
        depth += 1 if m.group(0) == '<div' else -1
        if depth == 0:
            return start + m.end()
    raise ValueError('unbalanced div')


def sections(s):
    """{lang: (start, end)} for every top-level language section, start includes the <!-- XX --> comment."""
    res = {}
    for m in re.finditer(r'(?:[ \t]*<!-- [A-Z]{2} -->\n)?[ \t]*<div class="lang-section[^"]*" id="section-([a-z]{2})">', s):
        start = m.start()
        div_start = s.index('<div', m.start())
        end = div_end(s, div_start)
        if end < len(s) and s[end] == '\n':
            end += 1
        res[m.group(1)] = (start, end)
    return res


def page_title(s, l):
    blk = re.search(r'const pageTitles = \{(.*?)\};', s, re.S).group(1)
    m = re.search(r"\b%s:\s*'((?:[^'\\]|\\.)*)'" % l, blk)
    return m.group(1).replace("\\'", "'") if m else None


def description(section_html):
    for p in re.findall(r'<p[^>]*>(.*?)</p>', section_html, re.S):
        t = html.unescape(re.sub(r'<[^>]+>', '', p)).strip()
        t = re.sub(r'\s+', ' ', t)
        if len(t) > 60:
            if len(t) > 158:
                t = t[:155].rsplit(' ', 1)[0].rstrip(',.;:') + '...'
            return t
    return None


def build(src, l, s, secs):
    keep_start, keep_end = secs[l]
    kept = s[keep_start:keep_end]
    kept = re.sub(r'<!-- [A-Z]{2} -->\n', '', kept)
    kept = re.sub(r'class="lang-section[^"]*"', 'class="lang-section active"', kept, count=1)
    # cut all language sections, then put back the kept one where the first was
    first = min(a for a, b in secs.values())
    out, pos = [], 0
    for a, b in sorted(secs.values()):
        out.append(s[pos:a])
        if a == first:
            out.append(kept)
        pos = b
    out.append(s[pos:])
    p = ''.join(out)

    url = '%s/%s/%s' % (SITE, l, src)
    title = page_title(s, l)
    desc = description(kept)
    p = p.replace('<html lang="en">', '<html lang="%s">' % l, 1)
    if title:
        p = re.sub(r'<title>.*?</title>', '<title>%s</title>' % html.escape(title, quote=False), p, count=1, flags=re.S)
        p = re.sub(r'<meta property="og:title" content="[^"]*">',
                   '<meta property="og:title" content="%s">' % html.escape(title.replace(' | TankSmart', '')), p, count=1)
    if desc and l != 'en':
        p = re.sub(r'<meta name="description" content="[^"]*">', '<meta name="description" content="%s">' % html.escape(desc), p, count=1)
        p = re.sub(r'<meta property="og:description" content="[^"]*">', '<meta property="og:description" content="%s">' % html.escape(desc), p, count=1)
    p = re.sub(r'\s*<link rel="canonical" href="[^"]*">', '', p)
    p = re.sub(r'\s*<link rel="alternate" hreflang="[^"]*" href="[^"]*">', '', p)
    p = re.sub(r'<meta property="og:url" content="[^"]*">', '<meta property="og:url" content="%s">' % url, p, count=1)
    alt = ['<link rel="canonical" href="%s">' % url]
    alt += ['<link rel="alternate" hreflang="%s" href="%s/%s/%s">' % (x, SITE, x, src) for x in LANGS]
    alt.append('<link rel="alternate" hreflang="x-default" href="%s/%s/%s">' % (SITE, DEFAULT, src))
    p = p.replace('</head>', '\n'.join(alt) + '\n</head>', 1)

    # paths: pages live one folder down now
    p = p.replace('src="assets/', 'src="/assets/').replace('href="assets/', 'href="/assets/')
    p = p.replace('href="index.html"', 'href="/index.html?lang=%s"' % l)
    p = p.replace("'index.html?lang='", "'/index.html?lang='")
    # language menu opens the same page in the other language
    p = p.replace('onchange="setLang(this.value)"', "onchange=\"location.href='/'+this.value+'/%s'\"" % src)
    p = p.replace(INIT, "setLang('%s');" % l)
    p = p.replace('<option value="%s">' % l, '<option value="%s" selected>' % l, 1)
    return p


def redirects(pages):
    lines = ['# Generated by tools/split_languages.py. Old multilingual addresses go to the page in one language.']
    for src in pages:
        stem = src[:-5]
        for path in ('/' + src, '/' + stem):
            lines.append('%s lang=:lang /:lang/%s 301!' % (path, src))
        for l in LANGS:
            if l in BROWSER:
                for path in ('/' + src, '/' + stem):
                    lines.append('%s /%s/%s 301! Language=%s' % (path, l, src, BROWSER[l]))
        for path in ('/' + src, '/' + stem):
            lines.append('%s /%s/%s 301!' % (path, DEFAULT, src))
    for l in LANGS:
        lines.append('/%s /index.html?lang=%s 302' % (l, l))
        lines.append('/%s/ /index.html?lang=%s 302' % (l, l))
    return '\n'.join(lines) + '\n'


def sitemap(pages):
    today = date.today().isoformat()
    urls = ['  <url>\n    <loc>%s/</loc>\n    <lastmod>%s</lastmod>\n    <changefreq>weekly</changefreq>\n  </url>' % (SITE, today)]
    for src in pages:
        for l in LANGS:
            extra = '\n    <lastmod>%s</lastmod>\n    <changefreq>weekly</changefreq>' % today if src == 'blog.html' else ''
            urls.append('  <url>\n    <loc>%s/%s/%s</loc>%s\n  </url>' % (SITE, l, src, extra))
    return '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + '\n'.join(urls) + '\n</urlset>\n'


def main():
    pages = source_pages()
    if not pages:
        print('split_languages: no multilingual pages found')
        return 1
    n = 0
    for src in pages:
        s = read(src)
        secs = sections(s)
        missing = [l for l in LANGS if l not in secs]
        if missing:
            print('split_languages: %s skipped, missing %s' % (src, missing))
            continue
        for l in LANGS:
            write('%s/%s' % (l, src), build(src, l, s, secs))
            n += 1
    write('_redirects', redirects(pages))
    sm = sitemap(pages)
    write('sitemap.xml', sm)
    write('sitemap-tanksmart.xml', sm)
    print('split_languages: %d pages from %d sources' % (n, len(pages)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
