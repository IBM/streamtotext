import asyncio
import os
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


class SilentSourceTestCase(base.TestCase):
    async def test_get_chunk_audio(self):
        a_s = SilentAudioSource()
        chunk = await a_s.get_chunk()
        sample = b'\0\0' * 1600

        self.assertEqual(3200, len(chunk.audio))
        self.assertEqual(sample, chunk.audio)

        chunk = await a_s.get_chunk()
        self.assertEqual(b'\0'*len(chunk.audio), chunk.audio)

    async def test_get_chunk_delay(self):
        a_s = SilentAudioSource()
        start_time = time.time()

        chunk = await a_s.get_chunk()
        self.assertAlmostEqual(start_time, time.time(), delta=.01)

        chunk = await a_s.get_chunk()
        self.assertAlmostEqual(start_time + .1, time.time(), delta=.2)

        chunk = await a_s.get_chunk()
        self.assertAlmostEqual(start_time + .2, time.time(), delta=.2)


class EvenChunkIteratorTestCase(base.TestCase):
    async def test_uneven_chunks(self):
        audio1 = b'\0\0' * 160
        audio2 = b'\0\0' * 80
        audio3 = b'\0\0' * 240

        audios = (audio1, audio2, audio3)
        chunks = [audio.AudioChunk(time.time(), x, 2, 16000) for x in audios]

        for chunk in audio.EvenChunkIterator(iter(chunks), 100):
            self.assertEqual(200, len(chunk.audio))


class WaveSourceTestCase(base.TestCase):
    async def test_hello_44100_wave_get_chunk(self):
        path = os.path.join(
            os.path.dirname(__file__),
            'test_data/hello_44100.wav'
        )
        src = audio.WaveSource(path, chunk_frames=1000)
        chunks = []
        async with src.listen():
            async for chunk in src.chunks:
                chunks.append(chunk)

        for chunk in chunks[:-1]:
            self.assertEqual(2000, len(chunk.audio))
            self.assertEqual(2, chunk.width)
            self.assertEqual(44100, chunk.freq)

        full_chunk = audio.merge_chunks(chunks)
        self.assertEqual(2, full_chunk.width)
        self.assertEqual(44100, full_chunk.freq)


class SquelchedSourceTestCase(base.TestCase):
    async def test_detect_silent_level(self):
        a_s = audio.SquelchedSource(SilentAudioSource())
        level = await a_s.detect_squelch_level(detect_time=.2)
        self.assertEqual(level, a_s.squelch_level)
        self.assertEqual(0, level)

    async def test_get_silent_chunk(self):
        a_s = audio.SquelchedSource(SilentAudioSource(), squelch_level=0)
        async with a_s.listen():
            with self.assertRaises(asyncio.TimeoutError):
                await asyncio.wait_for(a_s.get_chunk(), .2)

    async def test_hello_44100_get_chunk(self):
        path = os.path.join(
            os.path.dirname(__file__),
            'test_data/hello_44100.wav'
        )
        wav = audio.WaveSource(path, chunk_frames=1000)
        a_s = audio.SquelchedSource(wav)
        level = await a_s.detect_squelch_level()

        chunks = []
        async with a_s.listen():
            async for chunk in a_s.chunks:
                chunks.append(chunk)

        full_chunk = audio.merge_chunks(chunks)
