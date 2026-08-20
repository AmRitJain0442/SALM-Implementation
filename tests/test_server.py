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
