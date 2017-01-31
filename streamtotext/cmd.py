import argparse
import asyncio

from streamtotext import audio
from streamtotext import transcriber

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


def explode_config_arg(arg):
    if not arg:
        return {}
    return dict([x.split('=') for x in arg.split(',')])


def cmd_transcribe(args):
    source_config = explode_config_arg(args.audio_source_config)
    trans_config = explode_config_arg(args.transcriber_config)

    if 'device_ndx' in source_config:
        source_config['device_ndx'] = int(source_config['device_ndx'])

    mic = audio.Microphone(**source_config)
    ts = transcriber.WatsonTranscriber(**trans_config)

    loop = asyncio.get_event_loop()
    tasks = [
        asyncio.ensure_future(ts.transcribe(mic)),
        asyncio.ensure_future(handle_events(ts)),
        asyncio.ensure_future(timeout(ts, 2))
    ]
    res = loop.run_until_complete(asyncio.gather(*tasks))


def main():
    parser = argparse.ArgumentParser(description='Speech to text utility.')
    subparsers = parser.add_subparsers(help='command')

    parser_transcribe = subparsers.add_parser(
        'transcribe', help='Transcribe an audio source.'
    )

    parser_transcribe.add_argument('audio_source',
                                   choices=['microphone'], help='Audio source')
    parser_transcribe.add_argument('--audio-source-config', type=str,
                                   help='foo=bar,baz=boo arguments for source',
                                   default='')
    parser_transcribe.add_argument('transcriber',
                                   choices=['watson'],
                                   help='Transcription service')
    parser_transcribe.add_argument('--transcriber-config', type=str,
                                   help='foo=bar,baz=boo arguments for '
                                        'transcriber',
                                   default='')
    parser_transcribe.set_defaults(func=cmd_transcribe)

    args = parser.parse_args()
    if 'func' in args:
        args.func(args)
