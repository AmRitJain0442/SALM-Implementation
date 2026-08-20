import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from salm.config import Config
from salm.server import SessionManager, create_app
from salm.expand import Hit
from salm.correct import Correction
from salm.pipeline import Utterance


@pytest.fixture
def client(tmp_path):
    config = Config()
    config.transcript_dir = tmp_path
    return TestClient(create_app(config))


def test_serves_the_caption_page(client):
    response = client.get("/")

    assert response.status_code == 200
    assert "SALM" in response.text


def test_publishes_the_glossary_to_the_browser(client):
    terms = client.get("/api/glossary").json()["terms"]

    assert any(t["canonical"] == "ARR" for t in terms)


def test_websocket_reports_idle_before_a_session_starts(client):
    with client.websocket_connect("/ws") as socket:
        message = socket.receive_json()

    assert message == {"type": "status", "state": "idle"}


def test_saves_a_transcript_in_both_formats(tmp_path):
    config = Config()
    config.transcript_dir = tmp_path
    manager = SessionManager(config)
    manager.utterances = [Utterance(
        raw="Orbeck's runs nightly",
        text="Orbex runs nightly",
        corrections=(Correction(heard="Orbeck's", canonical="Orbex", score=0.73),),
        expansions=(Hit(canonical="ARR", expansion="Annual Recurring Revenue"),),
    )]

    saved = manager.save_transcript()

    assert saved.exists()
    assert "Orbex runs nightly" in saved.read_text(encoding="utf-8")
    record = json.loads(saved.with_suffix(".jsonl").read_text(encoding="utf-8"))
    assert record["corrections"] == [["Orbeck's", "Orbex"]]


def test_saves_nothing_when_no_one_spoke(tmp_path):
    config = Config()
    config.transcript_dir = tmp_path
    manager = SessionManager(config)

    assert manager.save_transcript() is None
    assert list(tmp_path.iterdir()) == []


def test_demo_mode_streams_a_corrected_utterance_to_the_browser(tmp_path):
    """Exercises the whole path: audio -> VAD -> ASR -> correct -> websocket."""
    config = Config()
    config.transcript_dir = tmp_path
    config.demo_audio = (Path("eval/audio/j4.wav"),)
    config.demo_realtime = False

    with TestClient(create_app(config)).websocket_connect("/ws") as socket:
        assert socket.receive_json()["state"] == "idle"
        socket.send_json({"command": "start"})

        utterance = None
        for _ in range(12):
            message = socket.receive_json()
            if message["type"] == "utterance":
                utterance = message
                break

    assert utterance is not None, "no utterance reached the browser"
    # j4 says "Orbex ... CRIMS ...": Orbex is misheard and repaired,
    # CRIMS is recognised and expanded.
    assert "Orbex" in utterance["text"]
    assert "Client Risk Management System" in utterance["text"]
    assert utterance["corrections"][0]["canonical"] == "Orbex"


def test_publishing_after_the_browser_disconnects_does_not_raise(tmp_path):
    """The capture thread outlives the websocket; a closed loop must not kill it."""
    import asyncio

    config = Config()
    config.transcript_dir = tmp_path
    manager = SessionManager(config)

    loop = asyncio.new_event_loop()
    queue = asyncio.Queue()
    manager.attach(loop, queue)
    loop.close()

    manager._publish({"type": "status", "state": "stopped"})


def _write_glossary(path, *names):
    path.write_text(
        "terms:\n" + "".join(f"  - canonical: {n}\n    type: jargon\n" for n in names),
        encoding="utf-8",
    )


def test_a_term_added_while_the_server_runs_is_used_by_the_next_session(tmp_path):
    """Editing the glossary must not require a restart.

    The sidebar re-read the file on every request while the pipeline held a
    copy from startup, so a newly added term showed in the UI but silently
    never fired.
    """
    path = tmp_path / "terms.yaml"
    _write_glossary(path, "Alpha")

    config = Config()
    config.glossary = path
    config.transcript_dir = tmp_path
    manager = SessionManager(config)
    assert [t.canonical for t in manager.glossary.terms] == ["Alpha"]

    _write_glossary(path, "Alpha", "Beta")

    assert "Beta" in [t.canonical for t in manager.glossary.terms]


def test_a_broken_glossary_is_reported_rather_than_killing_the_session(tmp_path):
    path = tmp_path / "terms.yaml"
    path.write_text("terms:\n  - canonical: Alpha\n    typo: oops\n", encoding="utf-8")

    config = Config()
    config.glossary = path
    config.transcript_dir = tmp_path
    manager = SessionManager(config)

    published = []
    manager._publish = published.append
    manager.start()

    assert published, "starting with a broken glossary published nothing"
    assert published[0]["type"] == "error"
    assert "typo" in published[0]["message"]
