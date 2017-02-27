"""Toolkit for streaming audio to transcription services.

There are two major components of this toolkit:
:class:`audio.AudioSource` and
:class:`transcriber.Transcriber`.

A :class:`transcriber.Transcriber` obtains audio from an
:class:`audio.AudioSource`, provides it to a transcription service, and emits
a :class:`transcriber.TranscribeEvent` whenever some transcription is
completed.
"""
