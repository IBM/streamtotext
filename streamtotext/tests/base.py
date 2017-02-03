import fixtures

import asyncio
import testtools


def aio_loop_while(async_fn):
    def async_runner(self):
        async def loop_stop_wrapper(self, loop, async_fn):
            try:
                return await async_fn(self)
            finally:
                loop.stop()

        def exc_handler(loop, ctxt):
            loop.stop()

        loop = asyncio.get_event_loop()
        loop.set_exception_handler(exc_handler)
        loop.run_until_complete(loop_stop_wrapper(self, loop, async_fn))
        loop.run_forever()

    return async_runner


asynctest = aio_loop_while


class TestCase(testtools.TestCase):
    pass
