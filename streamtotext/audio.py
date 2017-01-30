import asyncio

from contextlib import contextmanager


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
    def __init__(self, device_ndx):
        self._device_ndx = device_ndx

    async def get_chunk(self):
        await asyncio.sleep(.1)
