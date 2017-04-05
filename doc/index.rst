.. streamtotext documentation master file, created by
   sphinx-quickstart on Sun Feb 26 19:32:51 2017.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to streamtotext's documentation!
========================================

``streamtotext`` is a library for performing streaming speech to text
transcription.


It heavily utilises ``asyncio`` in order to provide an event based
api for reading from and processing audio sources which can be sent to
various transcription backends. ``streamtotext`` is highly customizable:
users can provide custom sources for audio, mix and provide filters for audio,
as well as provide custom transcription backends.


.. include:: installation.rst



Why
===

Many speech transcription applications are best designed in a streaming
manner (as opposed to bulk processing of a recording). As an example a live
voice transcription application would almost certainly require this. Even an
application which does not require live transcription can benefit from the
lower latency provided by a streaming implementation where transcription
can happen in the background while the sound is still being recorded.


Currently, there is a lack of tooling to perform this task in Python and
writing the code to do so can be difficult and error prone.  We are providing
a toolkit to handle the transcription pipeline as an event stream in a way
that allows for highly customizable audio sources (e.g.  squelched microphone)
and transcription methods (e.g. local trigger before remote service).


.. include:: demo.rst



Additional Information
======================

.. toctree::
   :maxdepth: 1

   API Documentation <api/streamtotext>
