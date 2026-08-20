"""Local web server: live captions in the browser, nothing leaving the machine."""

from __future__ import annotations

import asyncio
import json
import threading
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse

from .audio import ArrayAudioSource, Microphone
from .config import Config
from .glossary import Glossary
from .pipeline import Pipeline, Utterance
from .session import Session

WEB = Path(__file__).resolve().parent.parent / "web"


class SessionManager:
    """Runs a capture session on a worker thread and fans results out to the UI."""

    def __init__(self, config: Config):
        self._config = config
        self._glossary = Glossary.load(config.glossary)
        self._loop: asyncio.AbstractEventLoop | None = None
        self._queue: asyncio.Queue | None = None
        self._thread: threading.Thread | None = None
        self._session: Session | None = None
        self._source = None
        self.utterances: list[Utterance] = []

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def attach(self, loop: asyncio.AbstractEventLoop, queue: asyncio.Queue) -> None:
        self._loop, self._queue = loop, queue

    def _publish(self, payload: dict) -> None:
        """Hand a message to the websocket, if anyone is still listening.

        The capture thread outlives the browser connection. When a tab closes,
        its event loop goes away and publishing would otherwise raise on the
        worker thread and kill the session mid-meeting. Losing the message is
        fine -- utterances are kept in `self.utterances` and still reach the
        saved transcript.
        """
        loop, queue = self._loop, self._queue
        if loop is None or queue is None or loop.is_closed():
            return
        try:
            loop.call_soon_threadsafe(queue.put_nowait, payload)
        except RuntimeError:
            pass

    def start(self) -> None:
        if self.running:
            return
        self.utterances = []

        hotwords = None
        if self._config.biasing_enabled:
            from .tokenize import to_token_sequence

            hotwords = [
                seq
                for phrase in self._glossary.biasing_phrases()
                if (seq := to_token_sequence(phrase, self._config.model_dir))
            ]

        pipeline = Pipeline(
            self._glossary,
            threshold=self._config.correction_threshold,
            policy=self._config.expansion_policy,
        )

        def on_utterance(u: Utterance) -> None:
            self.utterances.append(u)
            self._publish({
                "type": "utterance",
                "raw": u.raw,
                "text": u.text,
                "corrections": [
                    {"heard": c.heard, "canonical": c.canonical, "score": round(c.score, 3)}
                    for c in u.corrections
                ],
                "expansions": [
                    {"canonical": e.canonical, "expansion": e.expansion}
                    for e in u.expansions
                ],
            })

        self._session = Session(
            model_dir=self._config.model_dir,
            vad_model=self._config.vad_model,
            pipeline=pipeline,
            on_utterance=on_utterance,
            num_threads=self._config.num_threads,
            hotwords=hotwords,
            hotwords_score=self._config.hotwords_score if hotwords else 0.0,
        )
        if self._config.demo_audio:
            self._source = ArrayAudioSource.from_wavs(
                self._config.demo_audio, realtime=self._config.demo_realtime
            )
        else:
            self._source = Microphone()

        def worker() -> None:
            self._publish({"type": "status", "state": "listening"})
            try:
                self._session.run(self._source)
            except Exception as exc:                      # surface, never swallow
                self._publish({"type": "error", "message": str(exc)})
            finally:
                self._publish({"type": "status", "state": "stopped"})

        self._thread = threading.Thread(target=worker, daemon=True)
        self._thread.start()

    def stop(self) -> Path | None:
        if self._session:
            self._session.stop()
        if self._source:
            self._source.stop()
        if self._thread:
            self._thread.join(timeout=5)
        return self.save_transcript()

    def save_transcript(self) -> Path | None:
        if not self.utterances:
            return None
        directory = Path(self._config.transcript_dir)
        directory.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

        md = directory / f"{stamp}.md"
        md.write_text(
            f"# Transcript {stamp}\n\n"
            + "\n\n".join(u.text for u in self.utterances)
            + "\n",
            encoding="utf-8",
        )

        jsonl = directory / f"{stamp}.jsonl"
        with jsonl.open("w", encoding="utf-8") as fh:
            for u in self.utterances:
                fh.write(json.dumps({
                    "raw": u.raw,
                    "text": u.text,
                    "corrections": [[c.heard, c.canonical] for c in u.corrections],
                    "expansions": [[e.canonical, e.expansion] for e in u.expansions],
                }) + "\n")
        return md


def create_app(config: Config | None = None) -> FastAPI:
    config = config or Config()
    app = FastAPI(title="SALM")
    manager = SessionManager(config)

    @app.get("/")
    async def index():
        return FileResponse(WEB / "index.html")

    @app.get("/render.js")
    async def render_js():
        return FileResponse(WEB / "render.js", media_type="application/javascript")

    @app.get("/api/glossary")
    async def glossary():
        g = Glossary.load(config.glossary)
        return {"terms": [
            {"canonical": t.canonical, "expansion": t.expansion, "type": t.type}
            for t in g.terms
        ]}

    @app.websocket("/ws")
    async def ws(socket: WebSocket):
        await socket.accept()
        queue: asyncio.Queue = asyncio.Queue()
        manager.attach(asyncio.get_running_loop(), queue)

        async def pump():
            while True:
                await socket.send_json(await queue.get())

        pumping = asyncio.create_task(pump())
        try:
            await socket.send_json({
                "type": "status",
                "state": "listening" if manager.running else "idle",
            })
            while True:
                command = json.loads(await socket.receive_text()).get("command")
                if command == "start":
                    manager.start()
                elif command == "stop":
                    saved = manager.stop()
                    await socket.send_json({
                        "type": "saved",
                        "path": str(saved) if saved else None,
                    })
        except WebSocketDisconnect:
            pass
        finally:
            pumping.cancel()

    return app


app = create_app()
