import asyncio
import audioop
import collections
import time

import janus
import pyaudio

# Using a namedtuple for audio chunks due to their lightweight nature
AudioChunk = collections.namedtuple('AudioChunk',
                                    ['start_time', 'audio', 'width', 'freq'])


def chunk_sample_cnt(chunk):
    return int(len(chunk.audio) / chunk.width)


def merge_chunks(chunks):
    assert(len(chunks) > 0)
    audio = b''.join([x.audio for x in chunks])
    return AudioChunk(chunks[0].start_time,
                      audio,
                      chunks[0].width,
                      chunks[0].freq)


def split_chunk(chunk, sample_offset):
    offset = int(sample_offset * chunk.width)
    first_audio = memoryview(chunk.audio)[:-offset]
    second_audio = memoryview(chunk.audio)[offset:]
    first_chunk = AudioChunk(
        chunk.start_time, first_audio, chunk.width, chunk.freq
    )
    second_chunk = AudioChunk(
        chunk.start_time, second_audio, chunk.width, chunk.freq
    )
    return first_chunk, second_chunk


class EvenChunkIterator(object):
    def __init__(self, iterator, chunk_size):
        self._iterator = iterator
        self._chunk_size = chunk_size
        self._cur_chunk = None

    def __iter__(self):
        return self

    def __next__(self):
        sample_queue = collections.deque()

        ret_chunk_size = 0
        while ret_chunk_size < self._chunk_size:
            chunk = self._cur_chunk or next(self._iterator)
            self._cur_chunk = None
            cur_chunk_size = chunk_sample_cnt(chunk)
            ret_chunk_size += cur_chunk_size

            if ret_chunk_size < self._chunk_size:
                # We need more chunks, append to the sample queue and grab next
                sample_queue.append(chunk)
            elif ret_chunk_size == self._chunk_size:
                sample_queue.append(chunk)
            else:
                # We need to break up the chunk
                overshoot = ret_chunk_size - self._chunk_size
                ret_chunk, leftover_chunk = split_chunk(chunk, overshoot)
                sample_queue.append(ret_chunk)
                self._cur_chunk = leftover_chunk

        return merge_chunks(sample_queue)

    def __aiter__(self):
        return self

    async def __anext__(self):
        sample_queue = collections.deque()

        ret_chunk_size = 0
        while ret_chunk_size < self._chunk_size:
            chunk = self._cur_chunk or await self._iterator.__anext__()
            self._cur_chunk = None
            cur_chunk_size = chunk_sample_cnt(chunk)
            ret_chunk_size += cur_chunk_size

            if ret_chunk_size < self._chunk_size:
                # We need more chunks, append to the sample queue and grab next
                sample_queue.append(chunk)
            elif ret_chunk_size == self._chunk_size:
                sample_queue.append(chunk)
            else:
                # We need to break up the chunk
                overshoot = ret_chunk_size - self._chunk_size
                ret_chunk, leftover_chunk = split_chunk(chunk, overshoot)
                sample_queue.append(ret_chunk)
                self._cur_chunk = leftover_chunk

        return merge_chunks(sample_queue)


class _ListenCtxtMgr(object):
    def __init__(self, source):
        self._source = source

    async def __aenter__(self):
        await self._source.start()

    async def __aexit__(self, *args):
        await self._source.stop()


class AudioSourceChunkIterator(object):
    def __init__(self, source):
        self._source = source

    def __aiter__(self):
        return self

    async def __anext__(self):
        return await self._source.get_chunk()


class AudioSource(object):
    def __init__(self):
        self.running = False

    @property
    def chunks(self):
        return AudioSourceChunkIterator(self)

    def listen(self):
        return _ListenCtxtMgr(self)

    async def start(self):
        self.running = True

    async def stop(self):
        self.running = False


class AudioSourceProcessor(AudioSource):
    def __init__(self, source):
        self._source = source

    async def start(self):
        await super(AudioSourceProcessor, self).start()
        await self._source.start()

    async def stop(self):
        await self._source.stop()
        await super(AudioSourceProcessor, self).stop()


class Microphone(AudioSource):
    def __init__(self,
                 audio_format=pyaudio.paInt16,
                 channels=1,
                 rate=16000,
                 device_ndx=0):
        super(Microphone, self).__init__()
        self._format = audio_format
        self._channels = channels
        self._rate = rate
        self._device_ndx = device_ndx
        self._pyaudio = None
        self._stream = None
        self._stream_queue = None

    async def start(self):
        await super(Microphone, self).start()
        loop = asyncio.get_event_loop()
        self._stream_queue = janus.Queue(loop=loop)

        self._pyaudio = pyaudio.PyAudio()
        self._stream = self._pyaudio.open(
            input=True,
            format=self._format,
            channels=self._channels,
            rate=self._rate,
            input_device_index=self._device_ndx,
            stream_callback=self._stream_callback
        )

    async def stop(self):
        await super(Microphone, self).stop()
        self._stream.close()
        self._pyaudio.terminate()

    async def get_chunk(self):
        raw_chunk = await self._stream_queue.async_q.get()
        return AudioChunk(start_time=raw_chunk[0]['input_buffer_adc_time'],
                          audio=raw_chunk[1], freq=self._rate, width=2)

    def _stream_callback(self, in_data, frame_count,
                         time_info, status_flags):
        self._stream_queue.sync_q.put((time_info, in_data))
        retflag = pyaudio.paContinue if self.running else pyaudio.paComplete
        return (None, retflag)


class RateConvert(AudioSource):
    def __init__(self, source, n_channels, in_rate, out_rate):
        super(RateConvert, self).__init__(source)
        self._n_channels = n_channels
        self._in_rate = in_rate
        self._out_rate = out_rate

    async def get_chunk(self):
        chunk = await self._source.get_chunk()
        return chunk


class SquelchedSource(AudioSourceProcessor):
    def __init__(self, source, sample_size=1600, squelch_level=None,
                 prefix_samples=2):
        super(SquelchedSource, self).__init__(source)
        self._recent_chunks = collections.deque(maxlen=prefix_samples)
        self._sample_size = sample_size
        self.squelch_level = squelch_level
        self._prefix_samples = prefix_samples
        self._sample_width = 2
        self._squelch_triggered = False
        self._even_iter = EvenChunkIterator(self._source.chunks,
                                            chunk_size=1600)

    async def detect_squelch_level(self, detect_time=10, threshold=.8):
        start_time = time.time()
        end_time = start_time + detect_time
        audio_chunks = collections.deque()
        async with self._source.listen():
            even_iter = EvenChunkIterator(self._source.chunks,
                                         self._sample_size)
            while time.time() < end_time:
                audio_chunks.append(await even_iter.__anext__())

        rms_vals = [audioop.rms(x.audio, self._sample_width) for x in
                    audio_chunks
                    if len(x.audio) == self._sample_size * self._sample_width]
        level = sorted(rms_vals)[int(threshold * len(rms_vals)):][-1]
        self.squelch_level = level
        return level

    async def start(self):
        assert(self.squelch_level is not None)
        await super(SquelchedSource, self).start()

    async def get_chunk(self):
        while True:
            chunk = await self._even_iter.__anext__()
            self._recent_chunks.append(chunk)

            if self._is_over_squelch(self._recent_chunks):
                return merge_chunks(self._recent_chunks)

    def _is_over_squelch(self, chunks):
        rms = audioop.rms(merge_chunks(chunks).audio, chunks[0].width)
        if self._squelch_triggered:
            if rms < (self.squelch_level * .8):
                self._squelch_triggered = False
                return False
            else:
                return True
        else:
            if rms > self.squelch_level:
                self._squelch_triggered = True
                return True
            else:
                return False
