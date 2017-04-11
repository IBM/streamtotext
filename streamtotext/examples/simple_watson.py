import asyncio

from streamtotext import audio, transcriber


async def handle_event(event):
    """This is called whenever we have new transcription information."""
    print(event)


def transcribe_wav_file(path, watson_user, watson_pass):
    # Create an audio source from the wav file
    wav_src = audio.WaveSource(path)

    # Create a transcriber for watson which will read from our audio source
    ts = transcriber.WatsonTranscriber(wav_src, 44100,
                                       watson_user, watson_pass)

    # Register our handle_event method to be called when transcription occurs
    ts.register_event_handler(handle_event)

    # Run transcription
    loop = asyncio.get_event_loop()
    loop.run_until_complete(ts.transcribe())
