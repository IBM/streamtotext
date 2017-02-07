import asyncio
import time

from streamtotext import audio
from streamtotext.tests import base

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
                return ret
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


class IsApproximatelyMismatch(object):
    def __init__(self, actual, value, margin):
        self.actual = actual
        self.value = value
        self.margin = margin

    def describe(self):
        return "%r is not within a margin of %r from %r" % (
            self.actual, self.margin, self.value)

    def get_details(self):
        return {}


class IsApproximately(object):
    def __init__(self, value, margin):
        self.value = value
        self.margin = margin

    def __str__(self):
        return 'IsApproximately(%r, %r)' % (self.value, self.margin)

    def __repr__(self):
        return self.__str__()

    def match(self, actual):
        if ((self.value > (actual - self.margin)) and
            (self.value < (actual + self.margin))):
            return None
        else:
            return IsApproximatelyMismatch(actual, self.value, self.margin)


class SilentSourceTestCase(base.TestCase):
    @base.asynctest
    async def test_get_chunk_audio(self):
        a_s = SilentAudioSource()
        chunk = await a_s.get_chunk()
        sample = b'\0\0' * 1600

        self.assertEqual(3200, len(chunk.audio))
        self.assertEqual(sample, chunk.audio)

        chunk = await a_s.get_chunk()
        self.assertEqual(b'\0'*len(chunk.audio), chunk.audio)

    @base.asynctest
    async def test_get_chunk_delay(self):
        a_s = SilentAudioSource()
        start_time = time.time()

        chunk = await a_s.get_chunk()
        self.assertThat(start_time, IsApproximately(time.time(), .01))

        chunk = await a_s.get_chunk()
        self.assertThat(start_time + .1, IsApproximately(time.time(), .1))

        chunk = await a_s.get_chunk()
        self.assertThat(start_time + .2, IsApproximately(time.time(), .1))


class EvenChunkIteratorTestCase(base.TestCase):
    @base.asynctest
    async def test_uneven_chunks(self):
        audio1 = b'\0\0' * 160
        audio2 = b'\0\0' * 80
        audio3 = b'\0\0' * 240

        audios = (audio1, audio2, audio3)
        chunks = [audio.AudioChunk(time.time(), x, 2, 16000) for x in audios]

        for i, chunk in enumerate(audio.even_chunk_iterator(chunks, 100)):
            self.assertEqual(200, len(chunk.audio))


class SquelchedSourceTestCase(base.TestCase):
    @base.asynctest
    async def test_detect_silent_level(self):
        a_s = audio.SquelchedSource(SilentAudioSource())
        level = await a_s.detect_squelch_level(detect_time=.5)
        self.assertEqual(level, a_s.squelch_level)
