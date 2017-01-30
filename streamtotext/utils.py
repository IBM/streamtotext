import asyncio

class InterrupError(Exception):
    pass


async def interruptable_get(queue, event, loop=None):
    loop = loop or asyncio.get_event_loop()
    trigger = asyncio.Event()
    _got_interrupt = False

    def got_interrupt():
        _got_interrupt = True

    get_fut = loop.create_future(queue.get())

    # fast path
    if get_fut.done():
        return get_fut.result()

    get_fut.add_done_callback(trigger.set)

    interrupt_fut = self._loop.create_future(event.wait())
    interrupt_fut.add_done_callback(got_interrupt)

    await trigger.wait()

    if not get_fut.done():
        get_fut.cancel()
    if not interrupt_fut.done():
        interrupt_fut.cancel()

    if _got_interrupt:
        raise InterruptError()
    return get_fut.result()
