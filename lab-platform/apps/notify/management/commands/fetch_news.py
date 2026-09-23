"""抓取 RSS 源入库实时动态（去重）；失败静默，可手动录入兜底。

宿主机 cron（可选，每小时）：
  docker exec lab-lab-1 python manage.py fetch_news
RSS 源配置：环境变量 LAB_NEWS_RSS（逗号分隔）或 settings 默认值。
"""

from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = '抓取 RSS 动态入库（AI/具身智能领域资讯）'

    def handle(self, *args, **options):
        from apps.notify.models import NewsItem

        rss_urls = _rss_sources()
        added = 0
        for url in rss_urls:
            items = _fetch(url)
            for title, link, published, summary in items:
                if NewsItem.objects.filter(title=title[:256]).exists():
                    continue
                NewsItem.objects.create(
                    id=NewsItem.next_id(), title=title[:256], source=_source_name(url),
                    url=link, summary=summary[:2000], published_at=published,
                    fetch_source=NewsItem.FETCH_RSS)
                added += 1
        self.stdout.write(self.style.SUCCESS(f'fetch_news done, sources={len(rss_urls)}, added={added}'))


def _rss_sources():
    import os
    raw = os.environ.get('LAB_NEWS_RSS', '').strip()
    return [u.strip() for u in raw.split(',') if u.strip()] or []


def _source_name(url):
    try:
        from urllib.parse import urlparse
        return urlparse(url).netloc
    except Exception:
        return ''


def _fetch(url):
    """拉取并解析 RSS/Atom。返回 [(title, link, datetime, summary)]。失败返回 []。"""
    import xml.etree.ElementTree as ET
    from datetime import datetime, timezone as dt_tz

    import requests

    try:
        resp = requests.get(url, timeout=15, headers={'User-Agent': 'Mozilla/5.0 LabNews/1.0'})
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
    except Exception:
        return []

    out = []
    entries = root.findall('.//item')
    if not entries:
        entries = root.findall('.//{http://www.w3.org/2005/Atom}entry')
    for e in entries[:30]:
        title = (e.findtext('title') or e.findtext('{http://www.w3.org/2005/Atom}title') or '').strip()
        link = e.findtext('link') or ''
        if not link:
            lk = e.find('{http://www.w3.org/2005/Atom}link')
            link = (lk.get('href') if lk is not None else '') or ''
        pub = e.findtext('pubDate') or e.findtext('{http://www.w3.org/2005/Atom}published') or ''
        summary = (e.findtext('description') or e.findtext('{http://www.w3.org/2005/Atom}summary') or '').strip()[:2000]
        if not title:
            continue
        published = _parse_date(pub) or timezone.now()
        out.append((title, link, published, summary))
    return out


def _parse_date(value):
    from email.utils import parsedate_to_datetime
    try:
        return parsedate_to_datetime(value)
    except Exception:
        try:
            return datetime.fromisoformat(value.replace('Z', '+00:00'))
        except Exception:
            return None