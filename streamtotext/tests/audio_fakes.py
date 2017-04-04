import asyncio
import time

from streamtotext import audio


class GeneratedAudioSource(audio.AudioSource):
    def __init__(self):
        super(GeneratedAudioSource, self).__init__()
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
            if delta < self._chunk_rate:
                await asyncio.sleep(delta)
                return await self.get_chunk()
            else:
                sample_cnt = int(delta * self._sample_rate)
                chunk = self.gen_sample(self._last_chunk_time, sample_cnt)
                self._last_chunk_time = time.time()
                return chunk

    def gen_sample(self, start_time, sample_cnt):
        pass


class SilentAudioSource(GeneratedAudioSource):
    def gen_sample(self, start_time, sample_cnt):
        sample = b'\0\0' * sample_cnt
        return audio.AudioChunk(start_time=start_time, audio=sample,
                                width=2, freq=self._sample_rate)
