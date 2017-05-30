import asyncio
import collections
import json
import os
from unittest import mock

import websockets.exceptions

from streamtotext import audio, transcriber
from streamtotext.tests import audio_fakes
from streamtotext.tests import base


class FakeTranscriber(transcriber.Transcriber):
    def __init__(self, source):
        super(FakeTranscriber, self).__init__(source)
        self._ev_queue = asyncio.Queue()

    async def _handle_audio_block(self, block):
        async for chunk in block:  # NOQA
            pass

    async def _read_events(self):
        await self._handle_event(None)
        while self.running:
            await self._handle_event(None)
            await asyncio.sleep(.1)


class EvHandler(object):
    def __init__(self, ts):
        self.ts = ts
        self.called = asyncio.Event()
        self.events = []

    async def handle(self, event):
        self.called.set()
        self.events.append(event)


class FakeTranscriberTestCase(base.TestCase):
    async def test_event_handler(self):
        ts = FakeTranscriber(audio_fakes.SilentAudioSource())
        handler = EvHandler(ts)
        ts.register_event_handler(handler.handle)
        async with ts:
            await handler.called.wait()


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
            async with ts:
                await handler.called.wait()


class PocketSphinxTranscriberTestCase(base.TestCase):
    async def test_transcribe(self):
        hello_path = os.path.join(
            os.path.dirname(__file__),
            'test_data/hello_44100.wav'
        )
        wav = audio.WaveSource(hello_path)
        sq_wav = audio.SquelchedSource(wav, squelch_level=200)
        cv_wav = audio.RateConvert(sq_wav, 1, 16000)
        ts = transcriber.PocketSphinxTranscriber.default_config(
            cv_wav
        )
        handler = EvHandler(ts)
        ts.register_event_handler(handler.handle)
        async with ts:
            await handler.called.wait()

        self.assertEqual(handler.events[0].results[0].transcript,
                         'hello')
