#!/usr/bin/env python3

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

import sys
import os
import subprocess as sub
import argparse
import tempfile
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from multiprocessing import cpu_count

from collections import namedtuple

# audiobook-split-ffmpeg.py
#
#  Split audiobook file into per-chapter files using chapter metadata and ffmpeg
#
#  See --help for usage
#
# More information in Github: https://github.com/MawKKe/audiobook-split-ffmpeg

# Special characters interpreted specially by most crappy software

CHR_BLACKLIST = ["\\", "/", ":", "*", "?", "\"", "<", ">", "|", "\0"]

def sanitize_string(original):
    """
    Filter typical special letters from string
    """
    if original is None:
        return None
    return ''.join(c for c in original if c not in CHR_BLACKLIST)

def parse_chapters(filename):
    """
    Read chapter metadata from 'filename' using ffprobe and return it as dict
    """

    command = ["ffprobe", '-i', filename, "-v", "error", "-print_format", "json", "-show_chapters"]
    try:
        # ffmpeg & ffprobe write output into stderr, except when
        # using -show_XXXX and -print_format. Strange.
        # Had we ran ffmpeg instead of ffprobe, this would throw since ffmpeg without
        # an output file will exit with exitcode != 0
        proc = sub.run(command, check=True, stdout=sub.PIPE, stderr=sub.PIPE)

        # .decode() will most likely explode if the ffprobe json output (chapter metadata)
        # was written with some weird encoding, and even more so if the data contains text in
        # multiple different text encodings...

        # TODO?
        # https://stackoverflow.com/questions/10009753/python-dealing-with-mixed-encoding-files
        output = proc.stdout.decode('utf8')

        data = json.loads(output)

        return data
    except sub.CalledProcessError as exn:
        print("ERROR: ", exn)
        print("FFPROBE-STDOUT: ", exn.stdout)
        print("FFPROBE-STDERR: ", exn.stderr)
        return None


# Helper type for collecting necessary information about chapter for processing
WorkItem = namedtuple("WorkItem",
                      ["infile", "outfile", "start", "end", "ch_num", "ch_max", "ch_title"])

def workitem_to_ffmpeg_cmd(w_item):
    """
    Build command list from WorkItem.
    The command list can be directly passed to subprocess.run() or similar.
    """

    # NOTE:
    # '-nostdin' param should prevent your terminal becoming all messed up
    # during the pool processing.  But if it does, you can fix it with 'reset'
    # and/or 'stty sane'.  If corruption still occurs, let me know (email is at
    # the top of the file).

    base_cmd = [
        "ffmpeg",
        "-nostdin",
        "-i", w_item.infile,
        "-v", "error",
        "-map_chapters", "-1",
        "-vn",
        "-c", "copy",
        "-ss", w_item.start,
        "-to", w_item.end,
        "-n"
    ]

    metadata_track = ["-metadata", "track={}/{}".format(w_item.ch_num, w_item.ch_max)]

    # TODO how does this handle mangled title values?
    metadata_title = ["-metadata", "title={}".format(w_item.ch_title)] if w_item.ch_title else []

    # Build the final command
    cmd = base_cmd + metadata_track + metadata_title + [w_item.outfile]

    return cmd

def main(argv):
    p = argparse.ArgumentParser(description="Split an audiobook chapters into files using ffmpeg")
    p.add_argument("--infile", required=True,
                   help="Input file. Chapter information must be present in file metadata")
    p.add_argument("--outdir", required=False,
                   help="Output directory. If omitted, a random directory under /tmp/ is used")
    p.add_argument("--concurrency", required=False, type=int, default=cpu_count(),
                   help="Number of concurrent ffmpeg worker processes")
    p.add_argument("--no-enumerate-filenames", required=False, dest='enumerate_files', action='store_false',
            help="Do not include chapter numbers in the output filenames")
    p.add_argument("--no-use-title", "--no-use-title-as-filename", required=False, dest='use_title', action='store_false',
            help="Do not include chapter titles in the output filenames (in case the titles are unusable/garbage)")
    p.add_argument("--dry-run", required=False, action='store_true',
                   help="Show what actions would be taken without taking them")
    p.add_argument("--verbose", required=False, action="store_true",
                   help="Show more output")

    args = p.parse_args(argv[1:])

    if not args.use_title and not args.enumerate_files:
        print("ERROR!")
        print("Options --no-use-title-as-filename and --no-enumerate-filenames given at the same time.")
        print("This would cause all output files to have identical names!")
        print("Remove either option and try again.")
        return -1

    if args.verbose:
        print("args:")
        print(args)
        print("---")

    fbase, fext = os.path.splitext(os.path.basename(args.infile))

    if 0 in [len(fbase), len(fext)]:
        print("Something is wrong, basename or file extension is empty")
        return -1

    if fext.startswith("."):
        fext = fext[1:]

    info = parse_chapters(args.infile)

    if (info is None) or ("chapters" not in info) or (len(info["chapters"]) == 0):
        print("Could not parse chapters, exiting...")
        return -1

    if args.outdir:
        os.makedirs(args.outdir, exist_ok=True)
        outdir = args.outdir
    else:
        outdir = tempfile.mkdtemp(prefix="ffmpeg-split-")

    if args.verbose:
        print("Output directory:", outdir)

    def validate_chapter(chap):
        start = chap['start']
        end = chap['end']
        if (end - start) <= 0:
            msg = "WARNING: chapter {0} duration <= 0 (start: {1}, end: {2}), skipping..."
            print(msg.format(chap['id'], start, end))
            return None
        return chap

    # Collect all valid chapters into a list
    chapters = list(filter(None, (validate_chapter(ch) for ch in info["chapters"])))

    # Find maximum chapter number
    max_chapter = max(chap['id'] for chap in chapters)

    # Produce equal-width zero-padded chapter numbers for use in filenames; makes sorting easier
    chnum_format = lambda n: '{n:{fill}{width}}'.format(n=n, fill='0', width=len(str(max_chapter)))

    # Compute output filename for chapter 'num' with 'title'.
    def outfile_basename(num, title_maybe):
        title = title_maybe if (args.use_title and title_maybe) else fbase
        base = "{title}.{ext}".format(title=title, ext=fext)
        if args.enumerate_files:
            return "{0} - {1}".format(chnum_format(num), base)
        return base

    # Chapter to title (string) or None
    def get_title_maybe(chap):
        if "tags" not in chap:
            return None
        return chap["tags"].get("title", None)

    def gen_workitems():
        for chapter in chapters:
            ch_num = chapter["id"] + 1 # chapter numbering starts at zero
            out_base = outfile_basename(ch_num, sanitize_string(get_title_maybe(chapter)))
            yield WorkItem(
                infile   = args.infile,
                outfile  = os.path.join(outdir, out_base),
                start    = chapter["start_time"],
                end      = chapter["end_time"],
                ch_num   = ch_num,
                ch_max   = max_chapter,
                ch_title = get_title_maybe(chapter)
            )

    work_items = list(gen_workitems())

    # FIXME: dry-run usually means "no side-effects". However, this
    # script will create the output directory in all cases.
    if args.dry_run:
        print("Dry run enabled. These commands would be run by workers:")
        print("---")
        for cmd in (workitem_to_ffmpeg_cmd(w_item) for w_item in work_items):
            print(cmd)
        print("---")
        print("Dry run complete. Exiting...")
        return 0

    print("Total: {0} chapters, concurrency: {1}".format(len(work_items), args.concurrency))

    n_jobs = 0
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        def start_all():
            for w_item in work_items:
                if args.verbose:
                    print("Submitting job: {}".format(w_item))
                yield pool.submit(ffmpeg_split, w_item), w_item

        futs = dict(start_all())
        n_jobs = len(futs)
        stats = wait_for_results(futs, args.verbose)


    print("---")
    print("Processing done")
    print("Total jobs: {tot}, Success: {success}, Errors: {error}".format(tot=n_jobs, **stats))
    if stats["error"] > 0:
        print("WARNING: there were errors. Some chapters may not have been processed correctly!")
    print("Output directory:", outdir)
    return 0

def wait_for_results(futs, verbose=False):
    """
    Collect ffmpeg processing results and display whether chapter was processed correctly
    """
    stats = {"success": 0, "error": 0}
    for fut in as_completed(futs):
        w_item = futs[fut]
        try:
            result = fut.result()
        # this looks nasty as hell, but hey, this is what they do in python docs..
        except Exception as exn_wtf:
            stats["error"] += 1
            print("ERROR: job '{}' generated an exeption: {}".format(w_item.outfile, exn_wtf))
        else:
            if result['ok']:
                stats["success"] += 1
                print("SUCCESS: {0}".format(w_item.outfile))
            else:
                stats["error"] += 1
                exn_proc = result["exn"]
                print("FAILURE: {0}".format(exn_proc.stderr.decode('utf8').strip()))
                if verbose:
                    print("Command that failed: {0}".format(result["cmd"]))
                    print("-"*5)
    return stats

def ffmpeg_split(w_item):

    cmd = workitem_to_ffmpeg_cmd(w_item)

    try:
        proc = sub.run(cmd, check=True, stdout=sub.PIPE, stderr=sub.PIPE)
        return {'ok': True, 'w_item': w_item, 'proc': proc, 'exn': None, 'cmd': cmd}
    except sub.CalledProcessError as exn:
        return {'ok': False, 'w_item': w_item, 'proc': None, 'exn': exn, 'cmd': cmd}


if __name__ == '__main__':
    sys.exit(main(sys.argv))
