# Copyright 2018 Markus Holmström (MawKKe)
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
CLI application implementation for audiobook-split-ffmpeg
"""

import os
import sys
import shlex
import argparse
import typing as t

from multiprocessing import cpu_count

from . import __version__
from .ffmpeg import workitem_to_ffmpeg_cmd, compute_workitems
from .workers import process_workitems


def parse_args(argv: t.List[str], mp3_default: bool = False) -> argparse.Namespace:
    """
    Parse argv into argparse.Namespace

    Arguments:

    argv
        a list of strings, usually the value of sys.argv

    mp3_default
        set default value of out-ext to `mp3`

    WARNING:
        If argv is malformed, the process will exit. Avoid using this function in tests.
    """
    parser = argparse.ArgumentParser(
        description='Split audiobook chapters using ffmpeg', epilog=f'version {__version__}'
    )

    infile_excl = parser.add_mutually_exclusive_group(required=True)
    infile_excl.add_argument(
        'infile_positional',
        nargs='*',
        help='Input file. Chapter information must be present in file metadata',
    )
    infile_excl.add_argument(
        '--infile',
        nargs='*',
        help='Input file. Chapter information must be present in file metadata',
    )

    parser.add_argument(
        '--outdir',
        required=False,
        default=None,
        help='Output directory. Created if does not exist yet.',
    )
    parser.add_argument(
        '--out-ext',
        required=False,
        default=("mp3" if mp3_default else None),
        help='New file extension. If conversion to another format is required.',
    )
    parser.add_argument(
        '--concurrency',
        required=False,
        type=int,
        default=cpu_count(),
        help='Number of concurrent ffmpeg worker processes',
    )

    # NOTE: without this mutual exclusion, the output
    # filenames would be identical between chapters!
    # In essence, you can give either (or neither), but not both.
    excl = parser.add_mutually_exclusive_group(required=False)
    excl.add_argument(
        '--no-enumerate-filenames',
        required=False,
        dest='enumerate_files',
        action='store_false',
        help='Do not include chapter numbers in the output filenames',
    )
    excl.add_argument(
        '--no-use-title',
        '--no-use-title-as-filename',
        required=False,
        dest='use_title',
        action='store_false',
        help='Do not include chapter titles in the output filenames',
    )

    parser.add_argument(
        '--dry-run',
        required=False,
        action='store_true',
        help='Show what actions would be taken without taking them',
    )
    parser.add_argument(
        '--verbose',
        required=False,
        action='store_true',
        help='Show more output',
    )

    args = parser.parse_args(argv[1:])
    args.infile = (args.infile_positional or args.infile)

    return args


def _main(args: argparse.Namespace) -> int:
    """
    CLI main function for audiobook-split-ffmpeg

    Arguments:

    args
        an argparse.Namespace() object containing the required command line arguments
        See parse_args() for more details.
    """

    if args.verbose:
        print('args:', args)

    def parse_path(*pathes):
        for _infile in map(os.path.abspath, pathes):
            if os.path.isfile(_infile):
                yield _infile
            elif os.path.isdir(_infile):
                yield from parse_path(
                    *map(lambda p: os.path.join(_infile, p), os.listdir(_infile))
                )
            else:
                raise RuntimeError("No path \"{0}\" was found".format(_infile))

    for infile in parse_path(*args.infile):

        outdir = args.outdir
        if outdir is None:
            outdir, _ = os.path.splitext(infile)

        work_items = list(
            compute_workitems(
                infile,
                outdir,
                enumerate_files=args.enumerate_files,
                use_title_in_filenames=args.use_title,
                out_ext=args.out_ext
            )
        )
        if args.verbose:
            print('Found: {0} chapters to be processed'.format(len(work_items)))

        if args.dry_run:
            print('# NOTE: dry-run requested')
            print(shlex.join(['mkdir', '-p', outdir]))
            commands = (workitem_to_ffmpeg_cmd(wi) for wi in work_items)
            escaped_cmds = (shlex.join(cmd) for cmd in commands)
            for cmd in escaped_cmds:
                print(cmd)
            return 0

        return_code = process_workitems(
            work_items,
            outdir,
            args.concurrency,
            args.verbose,
        )
        if return_code != 0:
            return return_code

    return 0


def main() -> t.NoReturn:
    """
    CLI main function for audiobook-split-ffmpeg
    """
    sys.exit(_main(parse_args(sys.argv)))


def main_mp3_mode() -> t.NoReturn:
    sys.exit(_main(parse_args(sys.argv, True)))


if __name__ == '__main__':
    main()
