Bulk Transcription
==================

Some transcription backends, such as :class:`audio.PocketSphinxTranscriber` do
not support streaming. In order to use these backends an
:class:`audio.BulkAudioSource` or :class:`audio.BulkAudioSourceProcessor` must
be used as the input audio source.


This is due to the fact that the standard audio source provides audio to
transcription services as it becomes available. In the case of a transcription
backend which only supports bulk transcription the backend needs to know when
to start and end a transcription request. For example, if we were transcribing
a recording over 2 seconds the transcription backend would likely get audio
samples every 100ms. Obviously, we want to make 1 bulk transcription request
for the full 2 second recording, not 20 100ms requests.


To solve this, a bulk audio source will only send audio to the transcription
backend in chunks appropriate for a bulk transcription. The
:class:`audio.Bulkify` source is the most basic form of this and it will
buffer an audio source until the audio source has ended and will then provide
the entire audio in a single chunk.
