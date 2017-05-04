import asyncio

from streamtotext import audio, transcriber


async def handle_event(event):
    """This is called whenever we have new transcription information."""
    print(event)


def transcribe_wav_file(path, watson_user, watson_pass):
    # Create an audio source from the wav file
    wav_src = audio.WaveSource(path)

    # Resample the audio to 16000hz which is what pocketsphinx expects
    cv_wav = audio.RateConvert(sq_wav, 1, 16000)

    # Bulkify the wav audio source. See `Bulk Transcription` doc.
    bulk_wav = audio.Bulkify(cv_wav)

    # Create a transcriber for pocketsphinx which will read from our audio
    # source
    ts = transcriber.PocketSphinxTranscriber.default_config(
        bulk_wav
    )

    # Register our handle_event method to be called when transcription occurs
    ts.register_event_handler(handle_event)

    # Run transcription
    loop = asyncio.get_event_loop()
    loop.run_until_complete(ts.transcribe())
