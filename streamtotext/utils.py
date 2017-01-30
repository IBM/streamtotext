import asyncio

class InterruptError(Exception):
    pass


async def interruptable_get(queue, event, loop=None):
    loop = loop or asyncio.get_event_loop()
    trigger = asyncio.Event()

    def set_trigger(future):
        trigger.set()

    get_fut = asyncio.ensure_future(queue.get())

    # fast path
    if get_fut.done():
        return get_fut.result()

    get_fut.add_done_callback(set_trigger)

    interrupt_fut = asyncio.ensure_future(event.wait())
    interrupt_fut.add_done_callback(set_trigger)

    await trigger.wait()

    if get_fut.done():
        interrupt_fut.cancel()
        return get_fut.result()
    get_fut.cancel()
    raise InterruptError
