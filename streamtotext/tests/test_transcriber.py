import asyncio
import collections
import json
from unittest import mock

import websockets.exceptions

from streamtotext import transcriber
from streamtotext.tests import audio_fakes
from streamtotext.tests import base


class FakeTranscriber(transcriber.Transcriber):
    def __init__(self, source):
        super(FakeTranscriber, self).__init__(source)
        self._ev_queue = asyncio.Queue()

    async def _send_chunk(self, chunk):
        pass

    async def _read_events(self):
        await self._handle_event(None)
        while self.running:
            await self._handle_event(None)
            await asyncio.sleep(.1)


class EvHandler(object):
    def __init__(self, ts, call_count=0):
        self.ts = ts
        self.called = False
        self.call_count = call_count

    async def handle(self, event):
        self.called = True
        if self.call_count <= 0:
            await self.ts.stop(wait=False)
        else:
            self.call_count -= 1


class FakeTranscriberTestCase(base.TestCase):
    async def test_event_handler(self):
        ts = FakeTranscriber(audio_fakes.SilentAudioSource())
        handler = EvHandler(ts)
        ts.register_event_handler(handler.handle)
        await ts.transcribe()
        self.assertEqual(handler.called, True)


class FakeWatsonWS(object):
    def __init__(self):
        self._sent_msgs = collections.deque()
        self.reset()
        self.recv_task = None

    async def connect(self):
        self.running = True
        return self

    async def send(self, data):
        self._sent_msgs.append(data)
        if isinstance(data, str):
            msg = json.loads(data)
            if msg.get('action') == 'start':
                self.listening = True
                await self._recv_msgs.put('{"state": "listening"}')
        elif isinstance(data, bytes):
            await self._recv_msgs.put('{ "results": [] }')

    async def recv(self):
        while self.running:
            self._recv_task = asyncio.ensure_future(self._recv_msgs.get())
            await self._recv_task
            try:
                return self._recv_task.result()
            except asyncio.CancelledError:
                raise websockets.exceptions.ConnectionClosed(500, "closed")

    def reset(self):
        self._recv_msgs = asyncio.Queue()
        self.running = False
        self.listening = False

    def close(self):
        self.reset()
        if not self._recv_task.done():
            self._recv_task.cancel()


class WatsonTranscriberTestCase(base.TestCase):
    async def test_transcribe(self):
        with mock.patch('websockets.connect') as mock_ws:
            fake_ws = FakeWatsonWS()
            mock_ws.return_value = fake_ws.connect()
            ts = transcriber.WatsonTranscriber(audio_fakes.SilentAudioSource(),
                                               16000, 'fakeuser', 'fakepass')
            handler = EvHandler(ts)
            ts.register_event_handler(handler.handle)
            await ts.transcribe()
            self.assertEqual(handler.called, True)
