Transcribe a wav file using pocketsphinx
========================================

In this example we take a WAV file recorded at 44100hz, we resample it to
16khz, then we bulkify it so it can be transcribed as a single file, then we
send it to pocketsphinx.


.. literalinclude:: ../../streamtotext/examples/simple_pocketsphinx.py
    :linenos:
    :language: python
