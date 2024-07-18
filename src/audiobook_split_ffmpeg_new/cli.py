import sys
import argparse
from pathlib import Path
import typing as t

import asyncio
from multiprocessing import cpu_count

from audiobook_split_ffmpeg_new import lib, model

import logging

logger = logging.getLogger(__name__)


async def process(
    commands: t.List[t.List[str]], max_concurrency: int
) -> t.Sequence[t.Optional[int]]:
    sem = asyncio.Semaphore(max_concurrency)

    async def run(cmd: t.List[str], fail: bool = False) -> t.Optional[int]:
        async with sem:
            logger.info('starting: %s', cmd[-1])
            proc = await asyncio.create_subprocess_exec(cmd[0], *cmd[1:])
            await proc.wait()
        logger.info('finished: %s', cmd[-1])
        return proc.returncode

    tasks = [asyncio.create_task(run(cmd)) for cmd in commands]

    return await asyncio.gather(*tasks)


def inner_main(argv: t.List[str]) -> int:
    logging.basicConfig(level=logging.INFO)
    p = argparse.ArgumentParser(prog=Path(argv[0]).name)
    p.add_argument('-i', '--infile', type=Path, required=True)
    p.add_argument('-o', '--outdir', type=Path, required=True)
    p.add_argument(
        '--input-encoding', type=str, help='Parse ffprobe output with this encoding (default: UTF8)'
    )
    p.add_argument(
        '--no-use-title-in-name',
        dest='use_title_in_name',
        action='store_false',
        help='Disable using chpater title as output filename stem',
    )
    p.add_argument(
        '--no-use-title-in-meta',
        dest='use_title_in_meta',
        action='store_false',
        help='Disable setting chapter title in output metadata',
    )
    p.add_argument(
        '--no-use-track-num-in-meta',
        dest='use_tracknum_in_meta',
        action='store_false',
        help='Disable setting track number in output metadata',
    )
    p.add_argument(
        '--track-num-offset',
        type=int,
        default=1,
        help='Offset track numbers by this much. Affects both output filename and metadata',
    )
    p.add_argument('--dump-chapters-and-stop', action='store_true')
    p.add_argument('-j', '--max-concurrency', type=int, default=cpu_count())

    args = p.parse_args(argv[1:])

    args.max_concurrency = 1 if args.max_concurrency < 1 else args.max_concurrency

    opts = model.Options(
        use_title_in_name=args.use_title_in_name,
        use_title_in_meta=args.use_title_in_meta,
        use_track_num_in_meta=args.use_tracknum_in_meta,
        track_enumeration_offset=args.track_num_offset,
    )

    info = lib.read_fileinfo(args.infile, args.input_encoding)

    if args.dump_chapters_and_stop:
        for ch in info.meta.chapters:
            print(ch)
        return 0

    args.outdir.mkdir(parents=True, exist_ok=True)

    def make_commands() -> t.Iterator[t.List[str]]:
        for i, ch in enumerate(info.meta.chapters):
            yield lib.make_ffmpeg_split_cmd(info=info, ch=ch, outdir=args.outdir, opts=opts)

    commands = list(make_commands())

    result = asyncio.run(process(commands, args.max_concurrency))

    print('result:', result)

    return 0


def main() -> t.NoReturn:
    sys.exit(inner_main(sys.argv))


if __name__ == '__main__':
    main()
