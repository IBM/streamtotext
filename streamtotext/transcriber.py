class TranscribeEvent(object):
    def __init__(self, results, final):
        self.results = results
        slef.final = final


class GoogleTranscribeEvent(TranscribeEvent):
    def __init__(self, results, final, stability):
        super(TranscribeEvent, self).__init__(results, final)
        self.stability = stability


class Transcriber(object):
    def __init__(self):
        self.running = False
        self._events = asyncio.Queue(100)

    async def transcribe(self, audio_source):
        self.running = True
        while self.running:
            await self._send_chunk(await audio_source.get_chunk())

    def stop(self):
        self.running = False

    async def all_events(self):
        while self.running:
            # We dont want to block forever if the service is stopped
            # while were waiting for an event, so we have to poll
            try:
                ev = self._events.get_nowait()
            except asyncio.QueueEmpty:
                await asyncio.sleep(.2)
            else:
                yield ev


class WatsonTranscriber(Transcriber):
    async def transcribe(self, audio_source):
        pass


class GoogleTranscriber(Transcriber):
    async def transcribe(self, audio_source):
        pass
