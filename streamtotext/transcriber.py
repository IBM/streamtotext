import asyncio
import base64
import json

import websockets

from streamtotext import audio, utils

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


class EventGenerator(object):
    def __init__(self, transcriber):
        self._transcriber = transcriber

    async def __aiter__(self):
        return self

    async def __anext__(self):
        ev = await self._transcriber.next_event()
        if ev is None:
            raise StopAsyncIteration
        return ev


class Transcriber(object):
    def __init__(self, source):
        self._source = source
        self.running = False
        self._stopped_running = asyncio.Event()

    @property
    def events(self):
        return EventGenerator(self)

    async def next_event(self):
        return None

    async def _start(self):
        self.running = True
        self._stopped_running.clear()

    async def transcribe(self):
        print('Transcribing...')
        await self._start()
        async with self._source.listen():
            try:
                while self.running:
                    await self._send_chunk(await self._source.get_chunk())
            except audio.NoMoreChunksError:
                await self._send_complete()

    async def send_complete(self):
        pass

    async def stop(self):
        self.running = False
        self._stopped_running.set()


class WatsonStartError(Exception):
    def __init__(self, msg):
        self._msg = msg

    def __str__(self):
        return 'Connection start failure. Got: %s' % msg


class WatsonTranscriber(Transcriber):
    def __init__(self, source, source_freq, user, passwd,
                 host='stream.watsonplatform.net',
                 uri_base='/speech-to-text/api/v1/recognize',
                 model='en-US_BroadbandModel'):
        super(WatsonTranscriber, self).__init__(source)
        self._source_freq = source_freq
        self._user = user
        self._passwd = passwd
        self._host = host
        self._uri_base = uri_base
        self._model = model
        self._ws = None

    async def _start(self):
        connect_url = 'wss://%s/%s' % (self._host, self._uri_base)
        auth_header = self._to_auth_header(self._user, self._passwd)
        print('Connecting to %s. Auth=%s' % (connect_url, auth_header))
        self._ws = await websockets.connect(
            connect_url,
            extra_headers={'Authorization': auth_header}
        )
        print('Done.')
        print('Sending start data.')
        await self._send_start(self._ws, self._source_freq)
        print('Done.')
        await super(WatsonTranscriber, self)._start()

    async def stop(self):
        self._ws.close()
        await super(WatsonTranscriber, self).stop()

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

    async def _send_chunk(self, audio_chunk):
        print('Sending chunk')
        await self._ws.send(audio_chunk.audio)
        print('Done')

    async def _send_complete(self):
        await self._ws.send(json.dumps({'action': 'stop'}))

    async def next_event(self):
        if self._ws is not None:
            read = await self._ws.recv()
            msg = json.loads(read)
            return self._msg_to_event(msg)
        else:
            return None

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


class GoogleTranscriber(Transcriber):
    pass
