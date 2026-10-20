"""Raspagem de notícias via RSS + análise de sentimento por léxico (PT/EN).

Escolha deliberada: RSS é o canal que os próprios sites oferecem para consumo automatizado
— mais estável e mais respeitoso que raspar HTML. Há limitação de taxa entre requisições.
O léxico é simples e transparente; o sentimento é tratado como sinal FRACO pelo conselho.
"""

from __future__ import annotations

import math
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import requests

DEFAULT_FEEDS = {
    "infomoney": "https://www.infomoney.com.br/feed/",
    "coindesk": "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "cointelegraph": "https://cointelegraph.com/rss",
    "yahoo": "https://feeds.finance.yahoo.com/rss/2.0/headline?s={symbol}&region=US&lang=en-US",
}

POS = {
    # pt
    "alta", "sobe", "subiu", "dispara", "disparou", "lucro", "recorde", "avanço", "avança",
    "valoriza", "valorização", "crescimento", "cresce", "supera", "otimismo", "compra", "aprova",
    "dividendos", "recupera", "forte", "ganho", "ganhos", "positivo", "upgrade",
    # en
    "surge", "surges", "rally", "rallies", "gain", "gains", "beat", "beats", "record", "growth",
    "bullish", "upgraded", "soar", "soars", "profit", "approval", "approved", "rise",
    "rises", "jump", "jumps", "strong", "outperform", "buy", "inflows", "adoption",
}
NEG = {
    # pt
    "queda", "cai", "caiu", "despenca", "despencou", "prejuízo", "perda", "perdas", "recua",
    "desvaloriza", "crise", "rebaixa", "rebaixamento", "pessimismo", "venda", "fraude",
    "investigação", "multa", "falência", "negativo", "fraco", "risco",
    # en
    "drop", "drops", "fall", "falls", "plunge", "plunges", "crash", "loss", "losses", "miss",
    "misses", "bearish", "downgrade", "downgraded", "lawsuit", "fraud", "hack", "hacked",
    "ban", "sell-off", "selloff", "weak", "outflows", "bankruptcy", "probe", "fine", "exploit",
}
NEGATORS = {"não", "nao", "sem", "not", "no", "never", "nunca"}
TOKEN = re.compile(r"[\wÀ-ÿ\-]+", re.UNICODE)


@dataclass(frozen=True)
class NewsItem:
    source: str
    title: str
    summary: str
    link: str
    published: datetime | None

    @property
    def text(self) -> str:
        return f"{self.title}. {self.summary}"


def score_text(text: str) -> float:
    """Sentimento em [-1, 1]: (pos − neg) / √(pos + neg + 1), com negação de 3 tokens."""
    toks = [t.lower() for t in TOKEN.findall(text)]
    pos = neg = 0
    for i, t in enumerate(toks):
        pol = 1 if t in POS else -1 if t in NEG else 0
        if pol and any(w in NEGATORS for w in toks[max(0, i - 3): i]):
            pol = -pol
        pos += pol > 0
        neg += pol < 0
    if pos + neg == 0:
        return 0.0
    return max(-1.0, min(1.0, (pos - neg) / math.sqrt(pos + neg + 1)))


_last_hit: dict[str, float] = {}


def fetch_feed(name: str, url: str, *, min_interval: float = 2.0,
               session: requests.Session | None = None) -> list[NewsItem]:
    host = re.sub(r"^https?://([^/]+).*", r"\1", url)
    wait = min_interval - (time.monotonic() - _last_hit.get(host, 0))
    if wait > 0:
        time.sleep(wait)
    _last_hit[host] = time.monotonic()
    s = session or requests.Session()
    r = s.get(url, headers={"User-Agent": "Mozilla/5.0 (Vorcaro research bot)"}, timeout=15)
    r.raise_for_status()
    return parse_rss(name, r.content)


def parse_rss(name: str, xml: bytes) -> list[NewsItem]:
    root = ET.fromstring(xml)
    out = []
    for it in root.iter("item"):
        def g(tag: str, it: ET.Element = it) -> str:
            return (it.findtext(tag) or "").strip()
        pub = None
        if g("pubDate"):
            try:
                pub = parsedate_to_datetime(g("pubDate")).astimezone(timezone.utc)
            except (TypeError, ValueError):
                pub = None
        summary = re.sub(r"<[^>]+>", " ", g("description"))
        out.append(NewsItem(name, g("title"), summary, g("link"), pub))
    return out


def symbol_sentiment(items: list[NewsItem], aliases: list[str],
                     half_life_hours: float = 6.0) -> tuple[float, int]:
    """Sentimento agregado para um ativo, ponderado por decaimento exponencial no tempo."""
    now = datetime.now(timezone.utc)
    pats = [re.compile(rf"\b{re.escape(a)}\b", re.I) for a in aliases]
    num = den = 0.0
    n = 0
    for it in items:
        if not any(p.search(it.text) for p in pats):
            continue
        age = (now - it.published).total_seconds() / 3600 if it.published else half_life_hours
        w = 0.5 ** (max(0.0, age) / half_life_hours)
        num += w * score_text(it.text)
        den += w
        n += 1
    return (num / den if den else 0.0), n
