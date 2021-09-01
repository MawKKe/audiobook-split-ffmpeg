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

import sys
import shlex
import argparse

from multiprocessing import cpu_count

from .util import compute_workitems
from .ffmpeg import workitem_to_ffmpeg_cmd
from .workers import process_workitems

def parse_args(argv):
    """
    Parse argv into argparse.Namespace

    Arguments:

    argv
        a list of strings, usually the value of sys.argv

    WARNING:
        If argv is malformed, the process will exit. Avoid using this function in tests.
    """
    parser = argparse.ArgumentParser(description="Split audiobook chapters using ffmpeg")
    parser.add_argument("--infile", required=True,
                        help="Input file. Chapter information must be present in file metadata")
    parser.add_argument("--outdir", required=True,
                        help="Output directory. Created if does not exist yet.")
    parser.add_argument("--concurrency", required=False, type=int, default=cpu_count(),
                        help="Number of concurrent ffmpeg worker processes")

    # NOTE: without this mutual exclusion, the output
    # filenames would be identical between chapters!
    # In essence, you can give either (or neither), but not both.
    excl = parser.add_mutually_exclusive_group(required=False)
    excl.add_argument("--no-enumerate-filenames", required=False, dest='enumerate_files',
                      action='store_false',
                      help="Do not include chapter numbers in the output filenames")
    excl.add_argument("--no-use-title", "--no-use-title-as-filename", required=False,
                      dest='use_title', action='store_false',
                      help="Do not include chapter titles in the output filenames")

    parser.add_argument("--dry-run", required=False, action='store_true',
                        help="Show what actions would be taken without taking them")
    parser.add_argument("--verbose", required=False, action="store_true",
                        help="Show more output")

    args = parser.parse_args(argv[1:])

    return args

def _main(args):
    """
    CLI main function for audiobook-split-ffmpeg

    Arguments:

    args
        an argparse.Namespace() object containing the required command line arguments
        See parse_args() for more details.
    """

    if args.verbose:
        print("args:", args)

    work_items = list(compute_workitems(args.infile, args.outdir,
                                        enumerate_files=args.enumerate_files,
                                        use_title_in_filenames=args.use_title))
    if args.verbose:
        print("Found: {0} chapters to be processed".format(len(work_items)))

    if args.dry_run:
        print("# NOTE: dry-run requested")
        print(shlex.join(["mkdir", "-p", args.outdir]))
        commands = (workitem_to_ffmpeg_cmd(wi) for wi in work_items)
        escaped_cmds = (shlex.join(cmd) for cmd in commands)
        for cmd in escaped_cmds:
            print(cmd)
        return 0

    return process_workitems(work_items, args.outdir, args.concurrency, args.verbose)

def main():
    """
    CLI main function for audiobook-split-ffmpeg
    """
    sys.exit(_main(parse_args(sys.argv)))

if __name__ == "__main__":
    main()
