import asyncio
import os
import time

from streamtotext import audio
from streamtotext.tests import audio_fakes
from streamtotext.tests import base


class AListIter(object):
    def __init__(self, src):
        self.src = src
        self._iter = iter(self.src)

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self._iter)
        except StopIteration:
            raise StopAsyncIteration()


class SilentSourceTestCase(base.TestCase):
    async def test_get_chunk_audio(self):
        a_s = audio_fakes.SilentAudioSource()
        block = await a_s.__anext__()
        chunk = await block.__anext__()
        sample = b'\0'

        self.assertAlmostEqual(3200, len(chunk.audio), delta=4)
        self.assertEqual(sample * len(chunk.audio), chunk.audio)

        chunk = await block.__anext__()
        self.assertEqual(b'\0' * len(chunk.audio), chunk.audio)

    async def test_get_chunk_delay(self):
        a_s = audio_fakes.SilentAudioSource()
        start_time = time.time()
        block = await a_s.__anext__()

        await block.__anext__()
        self.assertAlmostEqual(start_time, time.time(), delta=.01)

        await block.__anext__()
        self.assertAlmostEqual(start_time + .1, time.time(), delta=.2)

        await block.__anext__()
        self.assertAlmostEqual(start_time + .2, time.time(), delta=.2)


class ChunkTestCase(base.TestCase):
    async def test_split_join_chunk(self):
        chunk_audio = bytes(range(100))
        chunk = audio.AudioChunk(time.time(), chunk_audio, 2, 16000)
        left_chunk, right_chunk = audio.split_chunk(chunk, 20)
        cmp_chunk = audio.merge_chunks((left_chunk, right_chunk))
        self.assertEqual(chunk, cmp_chunk)


class EvenChunkIteratorTestCase(base.TestCase):
    async def test_uneven_chunks(self):
        audio1 = b'\0\0' * 160
        audio2 = b'\0\0' * 80
        audio3 = b'\0\0' * 240

        audios = (audio1, audio2, audio3)
        chunks = [audio.AudioChunk(time.time(), sample, 2, 16000)
                  for sample in audios]
        chunk_iter = AListIter(chunks)

        async for chunk in audio.EvenChunkIterator(chunk_iter, 100):
            self.assertEqual(200, len(chunk.audio))

    async def test_large_chunk(self):
        chunk_audio = bytes(range(100))
        large_chunk = audio.AudioChunk(time.time(), chunk_audio, 2, 16000)
        chunk_iter = AListIter((large_chunk,))
        chunks = []
        async for chunk in audio.EvenChunkIterator(chunk_iter, 10):
            chunks.append(chunk)
        self.assertEqual(5, len(chunks))
        self.assertEqual(large_chunk, audio.merge_chunks(chunks))


class WaveSourceTestCase(base.TestCase):
    async def test_hello_44100_wave_get_chunk(self):
        path = os.path.join(
            os.path.dirname(__file__),
            'test_data/hello_44100.wav'
        )
        src = audio.WaveSource(path, chunk_frames=1000)
        chunks = []
        async with src.listen():
            async for block in src:
                async for chunk in block:
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
        a_s = audio.SquelchedSource(audio_fakes.SilentAudioSource())
        level = await a_s.detect_squelch_level(detect_time=.2)
        self.assertEqual(level, a_s.squelch_level)
        self.assertEqual(0, level)

    async def test_get_silent_chunk(self):
        a_s = audio.SquelchedSource(audio_fakes.SilentAudioSource(),
                                    squelch_level=10)
        async with a_s.listen():
            with self.assertRaises(asyncio.TimeoutError):
                await asyncio.wait_for(a_s.__anext__(), .2)

    async def test_hello_44100_get_chunk(self):
        path = os.path.join(
            os.path.dirname(__file__),
            'test_data/hello_44100.wav'
        )
        wav = audio.WaveSource(path, chunk_frames=1000)
        a_s = audio.SquelchedSource(wav, squelch_level=200)

        block_cnt = 0
        chunks = []
        async with a_s.listen():
            async for block in a_s:
                block_cnt += 1
                async for chunk in block:
                    chunks.append(chunk)
        self.assertEqual(1, block_cnt)
        self.assertEqual(15, len(chunks))
