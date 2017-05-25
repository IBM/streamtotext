"""Transciption components

The main base class which is responsible for performing transcription is
:class:`Transcriber`.
"""

import asyncio
import base64
from contextlib import contextmanager
import json
import os

import websockets
try:
    import pocketsphinx
except ImportError:
    # This is a workaround for doc generation where dep cannot be installed
    # TODO(greghaynes): Only fail open during doc gen
    pass


class AlreadyRunningError(Exception):
    def __init__(self):
        super(AlreadyRunningError, self).__init__(
            'Object started when it is already running'
        )


class TranscribeResult(object):
    def __init__(self, transcript, confidence=None):
        self.transcript = transcript
        self.confidence = confidence

    def __str__(self):
        return 'TranscribeResult(transcript=%s, confidence=%s)' % (
            self.transcript, self.confidence
        )


class TranscribeEvent(object):
    def __init__(self, results, final):
        self.results = results
        self.final = final

    def __str__(self):
        ret = 'TranscribeEvent(results=[%s], final=%s)'
        results_str = ', '.join([str(x) for x in self.results])
        return ret % (results_str, self.final)


class GoogleTranscribeEvent(TranscribeEvent):
    def __init__(self, results, final, stability):
        super(TranscribeEvent, self).__init__(results, final)
        self.stability = stability


class Transcriber(object):
    """Base class for implementing a transcriber.

    Once :func:`transcribe` is called a transcriber awaits on get_chunk from
    an audio source and then streams them to a transcription service.

    :parameter source: Input audio source
    :type source: audio.AudioSource
    """
    def __init__(self, source):
        self._source = source
        self.running = False
        self._stopped_running = asyncio.Event()
        self._ev_handlers = []

    async def _start(self):
        if not self.running:
            self.running = True
            self._stopped_running.clear()
        else:
            raise AlreadyRunningError()

    async def transcribe(self):
        await self._start()
        try:
            audio_task = asyncio.ensure_future(self._handle_audio())
            read_task = asyncio.ensure_future(self._read_events())
            while self.running:
                waits = [task for task in (audio_task, read_task)
                         if not task.done()]
                done, pending = await asyncio.wait(
                    waits,
                    return_when=asyncio.FIRST_COMPLETED
                )
                for fut in done:
                    exc = fut.exception()
                    if exc:
                        raise exc

                if not pending:
                    break
            audio_task.cancel()
            read_task.cancel()
        finally:
            self._stopped_running.set()
            await self.stop()

    async def stop(self, wait=True):
        if self.running:
            self.running = False
        if wait:
            await self._stopped_running.wait()

    def register_event_handler(self, handler):
        self._ev_handlers.append(handler)

    async def _handle_event(self, event):
        for handler in self._ev_handlers:
            await handler(event)

    async def _handle_audio(self):
        async with self._source.listen():
            while self.running:
                async for block in self._source:
                    await self._handle_audio_block(block)


class WatsonStartError(Exception):
    def __init__(self, msg):
        super(WatsonStartError, self).__init__(
            'Connection start failure. Got: %s' % msg
        )


class WatsonTranscriber(Transcriber):
    def __init__(self, source, source_freq, user, password,
                 host='stream.watsonplatform.net',
                 uri_base='/speech-to-text/api/v1/recognize',
                 model='en-US_BroadbandModel'):
        super(WatsonTranscriber, self).__init__(source)
        self._source_freq = source_freq
        self._user = user
        self._passwd = password
        self._host = host
        self._uri_base = uri_base
        self._model = model
        self._ws = None

    async def _start(self):
        connect_url = 'wss://%s/%s' % (self._host, self._uri_base)
        auth_header = self._to_auth_header(self._user, self._passwd)
        self._ws = await websockets.connect(
            connect_url,
            extra_headers={'Authorization': auth_header}
        )
        await self._send_start(self._ws, self._source_freq)
        await super(WatsonTranscriber, self)._start()

    async def stop(self, wait=True):
        await self._send_complete()
        self._ws.close()
        await super(WatsonTranscriber, self).stop(wait)

    async def _send_start(self, ws, rate):
        start_data = {
            "action": "start",
            "content-type": "audio/l16;rate=%d" % rate,
            "continuous": True,
            "interim_results": True,
            "word_confidence": True,
            "timestamps": True,
            "max_alternatives": 3
        }
        await ws.send(json.dumps(start_data))
        msg = json.loads(await ws.recv())
        if msg.get('state') != 'listening':
            raise WatsonStartError(msg)

    async def _handle_audio_block(self, block):
        async for chunk in block:
            await self._send_chunk(chunk)

    async def _send_chunk(self, audio_chunk):
        await self._ws.send(bytes(audio_chunk.audio))

    async def _send_complete(self):
        await self._ws.send(json.dumps({'action': 'stop'}))

    async def _read_events(self):
        while self.running:
            try:
                read = await self._ws.recv()
            except websockets.exceptions.ConnectionClosed as e:
                break
            msg = json.loads(read)
            ev = self._msg_to_event(msg)
            await self._handle_event(ev)

    def _to_auth_header(self, user, passwd):
        seed = ':'.join((user, passwd))
        return ' '.join(('Basic',
                         base64.b64encode(seed.encode('utf-8')).decode()))

    def _msg_to_event(self, msg):
        t_rs = []
        for result in msg.get('results', [{}]):
            for alt in result.get('alternatives', []):
                t_rs.append(TranscribeResult(alt['transcript'],
                                             alt.get('confidence', None)))

        return TranscribeEvent(t_rs, msg.get('final', False))


class PocketSphinxTranscriber(Transcriber):
    """Local transcriber which uses pocketsphinx.

    Note: This transcriber does not support streaming. The audio source
    needs to emit events in bulk. See `Bulk Transcription`_ for more
    information.

    :parameter source: Input audio source
    :type source: audio.AudioSource

    .. _Bulk Transcription: ../bulk.html
    """
    def __init__(self, source, hmm_path, lm_path, dict_path):
        super(PocketSphinxTranscriber, self).__init__(source)
        self._decoder = None
        self.hmm_path = hmm_path
        self.lm_path = lm_path
        self.dict_path = dict_path

    @staticmethod
    def default_config(source, model_dir=None):
        model_dir = model_dir or '/usr/share/pocketsphinx/model/'
        hmm_path = os.path.join(model_dir, 'en-us/en-us')
        lm_path = os.path.join(model_dir, 'en-us/en-us.lm.bin')
        dict_path = os.path.join(model_dir, 'en-us/cmudict-en-us.dict')
        return PocketSphinxTranscriber(source, hmm_path, lm_path, dict_path)

    @contextmanager
    def utterance(self):
        self._decoder.start_utt()
        yield
        self._decoder.end_utt()

    async def _start(self):
        config = pocketsphinx.Decoder.default_config()
        config.set_string('-hmm', self.hmm_path)
        config.set_string('-lm', self.lm_path)
        config.set_string('-dict', self.dict_path)
        self._decoder = pocketsphinx.Decoder(config)
        await super(PocketSphinxTranscriber, self)._start()

    async def stop(self, wait=True):
        await super(PocketSphinxTranscriber, self).stop(wait)
        self._decoder = None

    async def _handle_audio_block(self, block):
        with self.utterance():
            async for audio_chunk in block:
                self._decoder.process_raw(audio_chunk.audio, False, False)
        hyp = self._decoder.hyp()
        res = TranscribeResult(hyp.hypstr)
        await self._handle_event(TranscribeEvent((res,), True))

    async def _read_events(self):
        pass
