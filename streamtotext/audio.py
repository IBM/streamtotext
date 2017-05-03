"""Audio source and audio processing compoenents

The two main base classes are :class:`AudioSource` which provides audio and
:class:`AudioProcessor` which act as a pipeline processor on another
:class:`AudioSource`.
"""


import asyncio
import audioop
import collections
import time
import wave

import janus
try:
    import pyaudio
except ImportError:
    # This is a workaround for doc generation where pyaudio cannot be installed
    pass


class NoMoreChunksError(Exception):
    pass


class NoDefaultInputDeviceError(Exception):
    def __init__(self):
        super(NoDefaultInputDeviceError, self).__init__(
            'No default input device'
        )


# Using a namedtuple for audio chunks due to their lightweight nature
AudioChunk = collections.namedtuple('AudioChunk',
                                    ['start_time', 'audio', 'width', 'freq'])
"""A sequence of audio samples.

Most notably, this is the object which is returned from
:func:`AudioSource.get_chunk`. More generally, this is the lowest level object
passed between audio processing components.

In order to make this object use minimal memory it is implemented as a
namedtuple.

:param start_time: Unix timestamp of the first sample.
:type start_time: int
:param audio: Bytes array of audio samples.
:type audio: bytes
:param width: Number of bytes per sample.
:type width: int
:param freq: Sampling frequency.
:type freq: int
"""


def chunk_sample_cnt(chunk):
    """Number of samples which occured in an AudioChunk

    :param chunk: The chunk to examine.
    :type chink: AudioChunk
    """
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
    first_audio = memoryview(chunk.audio)[:offset]
    second_audio = memoryview(chunk.audio)[offset:]
    first_chunk = AudioChunk(
        chunk.start_time, first_audio, chunk.width, chunk.freq
    )
    second_chunk = AudioChunk(
        chunk.start_time, second_audio, chunk.width, chunk.freq
    )
    return first_chunk, second_chunk


class EvenChunkIterator(object):
    """Iterate over chunks from an audio source in even sized increments.

    :parameter iterator: Iterator over audio chunks.
    :type iterator: Iterator
    :parameter chunk_size: Number of samples in resulting chunks
    :type chunk_size: int
    """
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
            sample_queue.append(chunk)

            if ret_chunk_size > self._chunk_size:
                # We need to break up the chunk
                merged_chunk = merge_chunks(sample_queue)
                ret_chunk, leftover_chunk = split_chunk(merged_chunk,
                                                        self._chunk_size)
                self._cur_chunk = leftover_chunk
                return ret_chunk

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
            sample_queue.append(chunk)

            if ret_chunk_size > self._chunk_size:
                # We need to break up the chunk
                merged_chunk = merge_chunks(sample_queue)
                ret_chunk, leftover_chunk = split_chunk(merged_chunk,
                                                        self._chunk_size)
                self._cur_chunk = leftover_chunk
                return ret_chunk

        return merge_chunks(sample_queue)


class _ListenCtxtMgr(object):
    def __init__(self, source):
        self._source = source

    async def __aenter__(self):
        await self._source.start()

    async def __aexit__(self, *args):
        await self._source.stop()


class AudioSourceChunkIterator(object):
    """Iterate over the chunks in an :class:`AudioSource`

    :param source: Source to iterate over.
    :type source: AudioSource
    """
    def __init__(self, source):
        self._source = source

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return await self._source.get_chunk()
        except NoMoreChunksError:
            raise StopAsyncIteration('No more chunks')


class AudioSource(object):
    """Base class for providing audio.

    All classes which provide audio in some form implement this class.
    Subclasses should override :func:`get_chunk` to await until it can return
    an :class:`AudioChunk`.

    """
    def __init__(self):
        self.running = False

    @property
    def chunks(self):
        """Async iterator over get_chunk"""
        return AudioSourceChunkIterator(self)

    def listen(self):
        """Listen to the AudioSource.

        :ret: Async context manager which starts and stops the AudioSource.
        """
        return _ListenCtxtMgr(self)

    async def start(self):
        """Start the audio source.

        This is where initialization / opening of audio devices should happen.
        """
        self.running = True

    async def stop(self):
        """Stop the audio source.

        This is where deinitialization / closing of audio devices should
        happen.
        """
        self.running = False

    async def get_chunk(self):
        """Get the next audio chunk from the source.

        Subclasses should override this method.

        :ret: Next audio chunk.
        :rtype: Audiochunk
        """
        pass


class AudioSourceProcessor(AudioSource):
    """Base class for being a pipeline processor of an class:`AudioSource`

    :parameter source: Input source
    :type source: AudioSource
    """
    def __init__(self, source):
        self._source = source

    async def start(self):
        """Start the input audio source.

        This is intended to be called from the base class, not directly.
        """
        await super(AudioSourceProcessor, self).start()
        await self._source.start()

    async def stop(self):
        """Stop the input audio source.

        This is intended to be called from the base class, not directly.
        """
        await self._source.stop()
        await super(AudioSourceProcessor, self).stop()


class Microphone(AudioSource):
    """Use a local microphone as an audio source.

    :parameter audio_format: Sample format, default paInt16
    :type audio: PyAudio format
    :parameter channels: Number of channels in microphone.
    :type channels: int
    :parameter rate: Sample frequency
    :type rate: int
    :parameter device_ndx: PyAudio device index
    :type device_ndx: int
    """
    def __init__(self,
                 audio_format=None,
                 channels=1,
                 rate=16000,
                 device_ndx=0):
        super(Microphone, self).__init__()
        audio_format = audio_format or pyaudio.paInt16
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
        self._stream.stop_stream()
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


class WaveSource(AudioSource):
    """Use a wave file as an audio source.

    :parameter wave_path: Path to wave file.
    :type wave_path: string
    :parameter chunk_frames: Chunk size to return from get_chunk
    :type chunk_frames: int
    """
    def __init__(self, wave_path, chunk_frames=None):
        self._wave_path = wave_path
        self._chunk_frames = chunk_frames
        self._wave_fp = None
        self._width = None
        self._freq = None
        self._channels = None

    async def start(self):
        await super(WaveSource, self).start()
        self._wave_fp = wave.open(self._wave_path)
        self._width = self._wave_fp.getsampwidth()
        self._freq = self._wave_fp.getframerate()
        self._channels = self._wave_fp.getnchannels()
        assert(self._channels <= 2)

    async def stop(self):
        self._wave_fp.close()
        await super(WaveSource, self).stop()

    async def get_chunk(self):
        frame_cnt = self._chunk_frames or self._wave_fp.getnframes()
        frames = self._wave_fp.readframes(frame_cnt)
        if self._channels == 2:
            frames = audioop.tomono(frames, self._width, .5, .5)
        if len(frames) == 0:
            raise NoMoreChunksError('No more frames in wav')
        chunk = AudioChunk(0, audio=frames, width=self._width,
                           freq=self._freq)
        return chunk


class RateConvert(AudioSourceProcessor):
    def __init__(self, source, n_channels, out_rate):
        super(RateConvert, self).__init__(source)
        self._n_channels = n_channels
        self._out_rate = out_rate
        self._state = None

    async def get_chunk(self):
        chunk = await self._source.get_chunk()
        new_aud, self._state = audioop.ratecv(chunk.audio, 2, self._n_channels,
                                              chunk.freq, self._out_rate,
                                              self._state)
        return AudioChunk(chunk.start_time, new_aud, 2, self._out_rate)


class Bulkify(AudioSourceProcessor):
    """Read in an :class:`AudioSource` and convert it in to a single chunk.

    This is useful for passing audio to a non-streaming transcriber.
    """
    async def get_chunk(self):
        chunks = []
        try:
            while True:
                chunks.append(await self._source.get_chunk())
        except NoMoreChunksError:
            if not chunks:
                raise

        if chunks:
            return merge_chunks(chunks)


class SquelchedSource(AudioSourceProcessor):
    """Filter out samples below a volume level from an audio source.

    This is useful to prevent constant transcription attempts of background
    noise, and also to correctly create a 'trigger window' where
    transcription attempts are made.

    A sliding window of prefix_samples size is inspected. When the rms of
    prefix_samples * sample_size samples surpasses the squelch_level this
    source begins to emit audio. Once the rms of the sliding window passes
    below 80% of the squelch level this source stop emitting audio.

    :parameter source: Input source
    :type source: AudioSource
    :parameter sample_size: Size of each sample to inspect.
    :type sample_size: int
    :parameter squelch_level: RMS value to trigger squelch
    :type squelch_level: int
    :parameter prefix_samples: Number of samples of sample_size to check
    :type prefix_samples: int
    """
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
            try:
                while time.time() < end_time:
                    audio_chunks.append(await even_iter.__anext__())
            except StopAsyncIteration:
                pass

        rms_vals = [audioop.rms(x.audio, self._sample_width) for x in
                    audio_chunks
                    if len(x.audio) == self._sample_size * self._sample_width]
        level = sorted(rms_vals)[int(threshold * len(rms_vals)):][0]
        self.squelch_level = level
        return level

    async def start(self):
        assert(self.squelch_level is not None)
        await super(SquelchedSource, self).start()

    async def get_chunk(self):
        while True:
            try:
                chunk = await self._even_iter.__anext__()
            except StopAsyncIteration:
                raise NoMoreChunksError('No more chunks')
            self._recent_chunks.append(chunk)

            was_triggered = self._squelch_triggered
            self._squelch_triggered = self.check_squelch(
                self.squelch_level,
                self._squelch_triggered,
                self._recent_chunks
            )
            if self._squelch_triggered:
                if not was_triggered:
                    return merge_chunks(self._recent_chunks)
                else:
                    return chunk

    def check_squelch(self, level, is_triggered, chunks):
        rms_vals = [audioop.rms(x.audio, x.width) for x in chunks]
        median_rms = sorted(rms_vals)[int(len(rms_vals) * .5)]
        if is_triggered:
            if median_rms < (level * .8):
                return False
            else:
                return True
        else:
            if median_rms > self.squelch_level:
                return True
            else:
                return False


class AudioPlayer(object):
    """Play audio from an audio source.

    This is not generally useful for transcription, but can be very useful
    in the development of :class:`AudioSource` or :class:`AudioProcessor`
    classes.

    :param source: Source to play.
    :type source: AudioSource
    :param width: Bytes per sample.
    :type width: int
    :param channels: Number of channels in output device.
    :type channels: int
    :param freq: Sampling frequency of output device.
    :type freq: int
    """
    def __init__(self, source, width, channels, freq):
        self._source = source
        self._width = width
        self._channels = channels
        self._freq = freq

    async def play(self):
        """Play audio from source.

        This method will block until the source runs out of audio.
        """
        p = pyaudio.PyAudio()
        stream = p.open(format=p.get_format_from_width(self._width),
                        channels=self._channels,
                        rate=self._freq,
                        output=True)

        async with self._source.listen():
            async for chunk in self._source.chunks:
                stream.write(chunk.audio)

        stream.stop_stream()
        stream.close()

        p.terminate()
