import asyncio

from streamtotext import audio
from streamtotext import transcriber

async def timeout(ts, secs):
    await asyncio.sleep(secs)
    print('Timeout reached')
    ts.stop()


async def handle_events(ts):
    while not ts.running:
        await asyncio.sleep(.1)

    async for ev in ts.events:
        print(ev)
    print('No more events')


def main():
    mic = audio.Microphone(1)
    ts = transcriber.WatsonTranscriber()

    loop = asyncio.get_event_loop()
    tasks = [
        asyncio.ensure_future(ts.transcribe(mic)),
        asyncio.ensure_future(handle_events(ts)),
        asyncio.ensure_future(timeout(ts, 2))
    ]
    res = loop.run_until_complete(asyncio.gather(*tasks))
