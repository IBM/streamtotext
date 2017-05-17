import asyncio
import os
import time

from streamtotext import audio
from streamtotext.tests import audio_fakes
from streamtotext.tests import base


class SilentSourceTestCase(base.TestCase):
    async def test_get_chunk_audio(self):
        a_s = audio_fakes.SilentAudioSource()
        chunk = await a_s.get_chunk()
        sample = b'\0\0' * 1600

        self.assertEqual(3200, len(chunk.audio))
        self.assertEqual(sample, chunk.audio)

        chunk = await a_s.get_chunk()
        self.assertEqual(b'\0' * len(chunk.audio), chunk.audio)

    async def test_get_chunk_delay(self):
        a_s = audio_fakes.SilentAudioSource()
        start_time = time.time()

        await a_s.get_chunk()
        self.assertAlmostEqual(start_time, time.time(), delta=.01)

        await a_s.get_chunk()
        self.assertAlmostEqual(start_time + .1, time.time(), delta=.2)

        await a_s.get_chunk()
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
        chunks = [audio.AudioChunk(time.time(), x, 2, 16000) for x in audios]

        for chunk in audio.EvenChunkIterator(iter(chunks), 100):
            self.assertEqual(200, len(chunk.audio))

    async def test_large_chunk(self):
        chunk_audio = bytes(range(100))
        large_chunk = audio.AudioChunk(time.time(), chunk_audio, 2, 16000)
        chunks = []
        for chunk in audio.EvenChunkIterator(iter((large_chunk,)), 10):
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
        a_s = audio.SquelchedSource(audio_fakes.SilentAudioSource())
        level = await a_s.detect_squelch_level(detect_time=.2)
        self.assertEqual(level, a_s.squelch_level)
        self.assertEqual(0, level)

    async def test_get_silent_chunk(self):
        a_s = audio.SquelchedSource(audio_fakes.SilentAudioSource(),
                                    squelch_level=0)
        async with a_s.listen():
            with self.assertRaises(asyncio.TimeoutError):
                await asyncio.wait_for(a_s.get_chunk(), .2)

    async def test_hello_44100_get_chunk(self):
        path = os.path.join(
            os.path.dirname(__file__),
            'test_data/hello_44100.wav'
        )
        wav = audio.WaveSource(path, chunk_frames=1000)
        a_s = audio.SquelchedSource(wav, squelch_level=200)

        chunks = []
        async with a_s.listen():
            async for chunk in a_s.chunks:
                chunks.append(chunk)

    async def test_hello_44100_get_blockified_chunk(self):
        path = os.path.join(
            os.path.dirname(__file__),
            'test_data/hello_44100.wav'
        )
        wav = audio.WaveSource(path, chunk_frames=1000)
        a_s = audio.SquelchedSource(wav, squelch_level=500, blockify=True)
        
        chunks = []
        async with a_s.listen():
            async for chunk in a_s.chunks:
                chunks.append(chunk)

        self.assertEqual(1, len(chunks))
