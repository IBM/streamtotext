import asyncio

import janus
import pyaudio

class _ListenCtxtMgr(object):
    def __init__(self, source):
        self._source = source

    async def __aenter__(self):
        await self._source.start()

    async def __aexit__(self, *args):
        await self._source.stop()


class AudioSource(object):
    def __init__(self):
        self.running = False

    def listen(self):
        return _ListenCtxtMgr(self)

    async def start(self):
        self.running = True

    async def stop(self):
        self.running = False


class Microphone(AudioSource):
    def __init__(self,
                 audio_format=pyaudio.paInt16,
                 channels=1,
                 rate=16000,
                 device_ndx=0):
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
        self._stream_queue = janus.Queue(loop)

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
        await asyncio.sleep(.1)

    def _stream_callback(self, in_data, frame_count,
                         time_info, status_flags):
        self._stream_queue.put((time_info, in_data))
        retflag = pyaudio.paContinue if self.running else pyaudio.paComplete
        return (None, retflag)
