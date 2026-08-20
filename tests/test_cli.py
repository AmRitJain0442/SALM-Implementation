"""The CLI is the first thing a new machine touches, so its guidance matters."""
import salm.__main__ as cli


def test_check_tells_you_how_to_get_missing_models(tmp_path, capsys, monkeypatch):
    from salm.config import Config

    missing = Config()
    missing.model_dir = tmp_path / "absent"
    missing.vad_model = tmp_path / "absent.onnx"
    monkeypatch.setattr(cli, "_config_for_check", lambda: missing, raising=False)

    code = cli.main(["check"])
    out = capsys.readouterr().out

    assert code == 1
    assert "scripts/setup.py" in out


def test_demo_uses_the_sample_glossary_not_the_live_one(tmp_path):
    """The bundled demo audio contains invented terms.

    Reading whatever glossary is installed makes the demo show no corrections,
    which looks like a broken build.
    """
    from salm.config import Config

    config = Config()
    chosen = cli._glossary_for(config, demo=True, override=None)

    assert chosen.name == "terms.example.yaml"


def test_a_glossary_override_wins_over_the_demo_default(tmp_path):
    from salm.config import Config

    override = tmp_path / "mine.yaml"
    override.write_text("terms: []\n", encoding="utf-8")

    chosen = cli._glossary_for(Config(), demo=True, override=str(override))

    assert chosen == override
