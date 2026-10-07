#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Text-only HyperSpace brain for the Hermes Gadget desktop simulator.

Install hermes-gadget in a separate environment, then run this script from it.
The SDK owns the WebSocket protocol, pairing and simulator; this file only
replaces the development server's echo response with a control-plane chat turn.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from hermes_gadget.devserver import EchoBrain, _console
from hermes_gadget_plugin import textfmt
from hermes_gadget_plugin.hub import DeviceHub, DeviceSession
from hermes_gadget_plugin.store import DeviceStore


def complete_text(base_url: str, messages: list[dict], model: str, timeout: float) -> str:
    """Ask the local control plane for one answer, without agent tools."""
    url = base_url.rstrip("/")
    if not url.endswith("/v1"):
        url += "/v1"
    payload = {"messages": messages, "stream": False, "surface": "desktop"}
    if model:
        payload["model"] = model
    request = Request(
        url + "/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "X-Hyperspace-Tools": "off"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            data = json.load(response)
    except HTTPError as error:
        detail = error.read(300).decode("utf-8", "replace")
        raise RuntimeError(f"Control plane HTTP {error.code}: {detail}") from error
    except (URLError, TimeoutError) as error:
        raise RuntimeError(f"Control plane non raggiungibile: {error}") from error
    choices = data.get("choices") or []
    answer = ((choices[0].get("message") or {}).get("content") if choices else "") or ""
    if not isinstance(answer, str) or not answer.strip():
        raise RuntimeError("Il control plane non ha restituito testo")
    return answer.strip()


class HyperSpaceBrain(EchoBrain):
    def __init__(self, base_url: str, model: str = "", timeout: float = 90):
        super().__init__(require_pairing=True, loopback=False)
        self.base_url, self.model, self.timeout = base_url, model, timeout
        self.history: dict[str, list[dict]] = {}

    async def on_text(self, session: DeviceSession, msg_id: str, text: str) -> None:
        previous = self._turns.get(session.device_id)
        if previous and not previous.done():
            previous.cancel()
        messages = self.history.get(session.device_id, []) + [{"role": "user", "content": text}]
        turn = f"{session.session_id}:{msg_id}"
        self._turns[session.device_id] = session.spawn(self._answer(session, turn, messages))

    async def _answer(self, session: DeviceSession, turn: str, messages: list[dict]) -> None:
        await session.turn_start(turn)
        try:
            await session.send_status("Anna sta pensando")
            answer = await asyncio.to_thread(
                complete_text, self.base_url, messages, self.model, self.timeout
            )
            # Keep a bounded, per-device conversation. Only completed turns count.
            self.history[session.device_id] = (messages + [
                {"role": "assistant", "content": answer}
            ])[-20:]
            await session.send_reply(textfmt.for_device(answer, session.charset), turn=turn)
            await session.send_status("")
            await session.turn_end(turn, "success")
        except asyncio.CancelledError:
            if not session.closed:
                await session.send_status("")
                await session.turn_end(turn, "cancelled")
            raise
        except Exception as error:
            if not session.closed:
                await session.send_notice(f"Errore: {error}")
                await session.send_status("")
                await session.turn_end(turn, "failure")

    async def on_new_session(self, session: DeviceSession) -> None:
        previous = self._turns.get(session.device_id)
        if previous and not previous.done():
            previous.cancel()
        self.history.pop(session.device_id, None)
        await session.send_notice("Nuova conversazione")

    async def on_utterance(self, session: DeviceSession, msg_id: str,
                           wav: bytes, seconds: float) -> None:
        await session.send_notice("Questa prova supporta solo messaggi di testo")


async def serve(args: argparse.Namespace) -> None:
    brain = HyperSpaceBrain(args.control_plane, args.model, args.timeout)
    hub = DeviceHub(DeviceStore(Path(args.state_dir)), brain,
                    host="127.0.0.1", port=args.port, path="/gadget")
    brain.hub = hub
    await hub.start()
    print(f"Gadget → HyperSpace: ws://127.0.0.1:{hub.bound_port}/gadget")
    print("Avvia il simulatore, poi digita 'approve CODICE' qui. 'quit' per uscire.")
    stop = asyncio.Event()
    console = asyncio.create_task(_console(hub, brain, stop))
    try:
        await stop.wait()
    finally:
        console.cancel()
        await hub.stop()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--control-plane", default="http://127.0.0.1:8085")
    parser.add_argument("--model", default="", help="Vuoto: modello predefinito del control plane")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--timeout", type=float, default=90)
    parser.add_argument("--state-dir", default="/private/tmp/hyperspace-gadget-text")
    asyncio.run(serve(parser.parse_args()))


if __name__ == "__main__":
    main()
