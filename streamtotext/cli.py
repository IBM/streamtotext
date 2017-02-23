import argparse
import asyncio
import os

import pyaudio

from streamtotext import audio
from streamtotext import transcriber
from streamtotext import utils

async def timeout(ts, secs):
    await asyncio.sleep(secs)
    print('Timeout reached')
    await ts.stop()


async def handle_events(ts):
    while not ts.running:
        await asyncio.sleep(.1)

    async for ev in ts.events:
        print(ev)
    print('No more events')


def hello_wave_source():
    wav_path = os.path.join(utils.wav_dir(), 'hello_44100.wav')
    return audio.WaveSource(wav_path, chunk_frames=1000)


def cmd_transcribe(args):
    try:
        user = os.environ['WATSON_SST_USER']
        passwd = os.environ['WATSON_SST_PASSWORD']
    except KeyError:
        raise CommandError('Missing WATSON_SST_USER or WATSON_SST_PASSWORD '
                           'environment variable.')

    mic = hello_wave_source()
    squelched = audio.SquelchedSource(mic, squelch_level=500)

    loop = asyncio.get_event_loop()

    ts = transcriber.WatsonTranscriber(squelched, 44100, user=user,
                                       passwd=passwd)

    tasks = [
        asyncio.ensure_future(ts.transcribe()),
        asyncio.ensure_future(handle_events(ts)),
        asyncio.ensure_future(timeout(ts, 200))
    ]
    res = loop.run_until_complete(asyncio.gather(*tasks))


def cmd_play(args):
    loop = asyncio.get_event_loop()

    wav = hello_wave_source()
    squelched = audio.SquelchedSource(wav, squelch_level=500)
    player = audio.AudioPlayer(squelched, 2, 1, 44100)
    loop.run_until_complete(player.play())


def cmd_list_devices(args):
    p = pyaudio.PyAudio()
    for i in range(p.get_device_count()):
        print(p.get_device_info_by_index(i).get('name'))


def cmd_device_info(args):
    p = pyaudio.PyAudio()
    print(p.get_device_info_by_index(args.device_index))


def main():
    parser = argparse.ArgumentParser(description='Speech to text utility.')
    subparsers = parser.add_subparsers(help='command')

    parser_transcribe = subparsers.add_parser(
        'transcribe', help='Transcribe an audio source.'
    )
    parser_transcribe.add_argument('transcriber',
                                   choices=['watson'],
                                   help='Transcription service')
    parser_transcribe.set_defaults(func=cmd_transcribe)

    parser_play = subparsers.add_parser(
        'play', help='Play an audio source.'
    )
    parser_play.set_defaults(func=cmd_play)

    parser_list_devices = subparsers.add_parser(
        'list-devices', help='List local audio devices')
    parser_list_devices.set_defaults(func=cmd_list_devices)

    parser_device_info = subparsers.add_parser(
        'device-info', help='Get info about a device',
    )
    parser_device_info.add_argument('device_index', type=int,
                                    help='Numbered device index')
    parser_device_info.set_defaults(func=cmd_device_info)

    args = parser.parse_args()
    args.func(args)
