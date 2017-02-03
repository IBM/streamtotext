import asyncio
import time

from streamtotext import audio
from tests import base

class SilentAudioSource(audio.AudioSource):
    def __init__(self):
        super(SilentAudioSource, self).__init__()
        self._last_chunk_time = None
        self._chunk_rate = .1
        self._sample_rate = 16000

    async def get_chunk(self):
        cur_time = time.time()
        if self._last_chunk_time is None:
            self._last_chunk_time = cur_time - self._chunk_rate
            return await self.get_chunk()
        else:
            delta = cur_time - self._last_chunk_time
            if delta < 0:
                await asyncio.sleep(-delta)
                return await self.get_chunk()
            else:
                sample_cnt = int(delta * self._sample_rate)
                sample = b'\0\0' * sample_cnt
                return audio.AudioChunk(start_time=time, audio=sample)


class SilentSourceTestCase(base.TestCase):
    @base.asynctest
    async def test_silent_get_chunk(self):
        a_s = SilentAudioSource()
        chunk = await a_s.get_chunk()
        sample = b'\0\0' * 1600

        self.assertEqual(3200, len(chunk.audio))
        self.assertEqual(sample, chunk.audio)

        chunk = await a_s.get_chunk()
        self.assertEqual(3200, len(chunk.audio))
        self.assertEqual(sample, chunk.audio)
