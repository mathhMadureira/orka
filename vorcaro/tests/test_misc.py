from decimal import Decimal

from vorcaro import config
from vorcaro.scraping.news import parse_rss, score_text, symbol_sentiment

RSS = b"""<?xml version="1.0"?><rss><channel>
<item><title>Bitcoin dispara e bate recorde</title><description>alta forte</description>
<link>http://x/1</link></item>
<item><title>Ethereum despenca apos hack</title><description>perdas</description>
<link>http://x/2</link></item>
</channel></rss>"""


def test_sentiment_lexicon_and_negation():
    assert score_text("Ações sobem com lucro recorde") > 0
    assert score_text("Bitcoin crash after exchange hack") < 0
    assert score_text("Empresa não teve lucro") < 0
    assert score_text("o tempo hoje") == 0


def test_rss_parse_and_symbol_filter():
    items = parse_rss("t", RSS)
    assert len(items) == 2
    s, n = symbol_sentiment(items, ["bitcoin", "btc"])
    assert n == 1 and s > 0


def test_config_loads_default(tmp_path):
    risk, bt = config.load("config/default.toml")
    assert risk.risk_per_trade == Decimal("0.005") and bt.risk is risk
