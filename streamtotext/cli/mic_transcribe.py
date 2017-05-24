import argparse
import asyncio
import os
import sys

from streamtotext import audio
from streamtotext import transcriber


def parse_args(argv):
    parser = argparse.ArgumentParser(description='Transcribe a microphone.')

    parser.add_argument('transcription_service',
                        help='Name of transcription service to use.',
                        type=str,
                        choices=['watson', 'google'])
    parser.add_argument('-u', '--username',
                        help='Username for service account (if applicable).',
                        type=str)
    parser.add_argument('-p', '--password',
                        help='Password for service account (if applicable).',
                        type=str)
    parser.add_argument('-c', '--channels',
                        help='Number of channels to record from mic.',
                        default=1,
                        type=int)
    parser.add_argument('-f', '--frequency',
                        help='Sampling frequency from mic.',
                        default=16000,
                        type=int)
    parser.add_argument('-d', '--device-index',
                        help='Device index for mic',
                        type=int)
    parser.add_argument('-S', '--no-squelch',
                        help='Send audio when mic is quiet.',
                        action='store_true')
    return parser.parse_args(argv)


def exit(error):
    print("ERROR: %s" % error, file=sys.stderr)
    sys.exit(1)


async def handle_transcribe_event(ev):
    print(ev)


def get_audio_source(channels, frequency, device_ndx=None):
    mic = audio.Microphone(
        channels=channels,
        rate=frequency,
        device_ndx=device_ndx)
    return mic


def transcribe_watson(loop, src, src_freq, username, password):
    ts = transcriber.WatsonTranscriber(src, src_freq,
                                       user=username, password=password)
    ts.register_event_handler(handle_transcribe_event)

    loop.run_until_complete(ts.transcribe())


def transcribe(args):
    loop = asyncio.get_event_loop()

    src = get_audio_source(args.channels, args.frequency,
                           args.device_index)

    if not args.no_squelch:
        src = audio.SquelchedSource(src, squelch_level=100)
        print('Detecting squelch level.')
        print('Please talk in to your microphone at a normal volume.')
        #loop.run_until_complete(src.detect_squelch_level())
        print('Completed detection squelch level.')

    service = args.transcription_service
    if service == 'watson':
        username = os.environ.get('WATSON_SST_USER') or args.username
        password = os.environ.get('WATSON_SST_PASSWORD') or args.password

        if not username:
            exit(error='You must specify a username.')
        if not password:
            exit(error='You must specify a password.')

        print('Beginning transcription.')
        transcribe_watson(loop, src, args.frequency, username, password)


def main():
    args = parse_args(sys.argv[1:])
    transcribe(args)
