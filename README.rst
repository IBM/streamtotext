============
streamtotext
============

A pluggable streaming transcription pipleline for Python.


Overview
========

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

