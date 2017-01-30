import asyncio

class TranscribeEvent(object):
    def __init__(self, results, final):
        self.results = results
        slef.final = final


class GoogleTranscribeEvent(TranscribeEvent):
    def __init__(self, results, final, stability):
        super(TranscribeEvent, self).__init__(results, final)
        self.stability = stability


class EventGenerator(object):
    def __init__(self, transcriber, events_queue):
        self._transcriber = transcriber
        self._events_queue = events_queue

    async def __aiter__(self):
        return self

    async def __anext__(self):
        if self._transcriber.running:
            # We dont want to block forever if the service is stopped
            # while were waiting for an event, so we have to poll
            try:
                ev = self._events_queue.get_nowait()
            except asyncio.QueueEmpty:
                await asyncio.sleep(.2)
            else:
                return ev
        else:
            raise StopAsyncIteration


class Transcriber(object):
    def __init__(self):
        self.running = False
        self._events = asyncio.Queue(100)

    @property
    def events(self):
        return EventGenerator(self, self._events)

    async def transcribe(self, audio_source):
        self.running = True
        while self.running:
            await self._send_chunk(await audio_source.get_chunk())

    def stop(self):
        self.running = False


class WatsonTranscriber(Transcriber):
    async def transcribe(self, audio_source):
        pass


class GoogleTranscriber(Transcriber):
    async def transcribe(self, audio_source):
        pass
