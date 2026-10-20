import json

from vorcaro.agents import Council, default_agents
from vorcaro.brokers import PaperBroker
from vorcaro.cli import main
from vorcaro.data.providers import synthetic
from vorcaro.engine.live import LiveConfig, LiveEngine
from vorcaro.risk import RiskManager


def _engine(tmp_path, dry_run):
    data = {f"S{k}": synthetic(800, seed=k, ar=-0.3, symbol=f"S{k}") for k in range(3)}
    broker = PaperBroker("100000", data=data)
    cfg = LiveConfig(list(data), interval_s=0, dry_run=dry_run, journal=tmp_path / "j.jsonl")
    return LiveEngine(broker, Council(default_agents()), RiskManager(), cfg), broker, cfg


def test_dry_run_never_sends_orders(tmp_path):
    eng, broker, cfg = _engine(tmp_path, dry_run=True)
    eng.run(cycles=2)
    assert broker.orders == []
    kinds = {json.loads(line)["kind"] for line in cfg.journal.read_text().splitlines()}
    assert "opportunity" in kinds


def test_execute_sends_bracketed_orders(tmp_path):
    eng, broker, cfg = _engine(tmp_path, dry_run=False)
    plans = eng.cycle()
    assert len(broker.orders) == len(plans) > 0
    assert all(o.stop_loss is not None and o.take_profit is not None for o in broker.orders)


def test_cli_patterns_and_omega(capsys):
    main(["patterns", "--source", "synthetic:-0.3", "--bars", "3000"])
    out = capsys.readouterr().out
    assert "significativos" in out and "fora da amostra" in out
    main(["omega", "--source", "synthetic", "--bars", "600"])
    assert "Ω=" in capsys.readouterr().out
