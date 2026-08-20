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
