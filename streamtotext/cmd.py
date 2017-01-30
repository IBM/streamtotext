import asyncio

from streamtotext import audio
from streamtotext import transcriber


async def handle_events(ts):
    async for event in ts.events:
        print(event)


def main():
    mic = audio.Microphone()
    ts = transcriber.WatsonTranscriber()

    loop = asyncio.get_event_loop()

    tasks = [
        ts.transcribe(mic),
        handle_events(ts)
    ]
    loop.run_until_complete(asyncio.gather(*tasks))
    loop.close()
