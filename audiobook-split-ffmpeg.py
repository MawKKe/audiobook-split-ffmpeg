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
import shlex

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

def validate_chapter(chap):
    """
    Checks that chapter is valid (i.e has valid length)
    """
    start = chap['start']
    end = chap['end']
    if (end - start) <= 0:
        msg = "WARNING: chapter {0} duration <= 0 (start: {1}, end: {2}), skipping..."
        print(msg.format(chap['id'], start, end))
        return None
    return chap


def get_title_maybe(chap):
    """
    Chapter to title (string) or None
    """
    if "tags" not in chap:
        return None
    return chap["tags"].get("title", None)

def compute_workitems(infile, outdir, enumerate_files=True, use_title_in_filenames=True):
    """
    Compute WorkItem's for each chapter to be processed. These WorkItems can be then used
    for launching ffmpeg processes (see ffmpeg_split)

    Arguments:

    infile
        Path to an audio(book) file. Must contain chapter information in its metadata.
    outdir
        Path to a directory where chapter files will be written. Must exist already.
    enumerate_files
        Include chapter numbers in output filenames?
    use_title_in_filenames
        Include chapter titles in output filenames?
    """

    in_root, in_ext = os.path.splitext(os.path.basename(infile))

    if 0 in [len(in_root), len(in_ext)]:
        raise RuntimeError("Unexpected input filename format - root part or extension is empty")

    # Make sure extension has no leading dots.
    in_ext = in_ext[1:] if in_ext.startswith(".") else in_ext

    # Get chapter metadata
    info = parse_chapters(infile)

    if (info is None) or ("chapters" not in info) or (len(info["chapters"]) == 0):
        raise RuntimeError("Could not parse chapters")

    # Collect all valid chapters into a list
    chapters = list(filter(None, (validate_chapter(ch) for ch in info["chapters"])))

    # Find maximum chapter number. Remember + 1 since enumeration starts at zero!
    ch_max = max(chap['id'] + 1 for chap in chapters)

    # Produces equal-width zero-padded chapter numbers for use in filenames.
    chnum_fmt = lambda n: '{n:{fill}{width}}'.format(n=n, fill='0', width=len(str(ch_max)))

    for chapter in chapters:
        # Get cleaned title or None
        title_maybe = sanitize_string(get_title_maybe(chapter))

        ch_num = chapter["id"] + 1

        # Use chapter title in output filename base unless disabled or not available.
        # Otherwise, use the root part of input filename
        title = title_maybe if (use_title_in_filenames and title_maybe) else in_root

        out_base = "{title}.{ext}".format(title=title, ext=in_ext)

        # Prepend chapter number if requested
        if enumerate_files:
            out_base = "{0} - {1}".format(chnum_fmt(ch_num), out_base)

        yield WorkItem(
            infile   = infile,
            outfile  = os.path.join(outdir, out_base),
            start    = chapter["start_time"],
            end      = chapter["end_time"],
            ch_num   = ch_num,
            ch_max   = ch_max,
            ch_title = get_title_maybe(chapter)
        )


def main(argv):
    """
    CLI wrapper for split_chapters
    """

    parser = argparse.ArgumentParser(description="Split audiobook chapters using ffmpeg")
    parser.add_argument("--infile", required=True,
                        help="Input file. Chapter information must be present in file metadata")
    parser.add_argument("--outdir", required=False,
                        help="Output directory. If omitted, a random directory under /tmp/ is used")
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

    if args.verbose:
        print("args:", args)

    if args.outdir:
        os.makedirs(args.outdir, exist_ok=True)
        outdir = args.outdir
    else:
        outdir = tempfile.mkdtemp(prefix="ffmpeg-split-")

    if args.verbose:
        print("Output directory:", outdir)

    work_items = list(compute_workitems(args.infile, outdir,
                                        enumerate_files=args.enumerate_files,
                                        use_title_in_filenames=args.use_title))
    if args.verbose:
        print("Found: {0} chapters to be processed".format(len(work_items)))

    if args.dry_run:
        return dump_workitem_commands(work_items)
    return process_workitems(work_items, args.concurrency, args.verbose)


def dump_workitem_commands(work_items):
    """
    Shows what ffmpeg commands would be run, without running them.
    """
    print("# NOTE: dry-run requested")
    for work_item in work_items:
        print(shlex.join(workitem_to_ffmpeg_cmd(work_item)))
    return 0

def process_workitems(work_items, concurrency=1, verbose=False):
    """
    Runs ffmpeg worker process for each WorkItem, parallellized with ThreadPoolExecutor
    """
    if verbose:
        print("Starting ThreadPoolExecutor with concurrency={0}".format(concurrency))

    n_jobs = 0
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        def start_all():
            for w_item in work_items:
                if verbose:
                    print("Submitting job: {}".format(w_item))
                yield pool.submit(ffmpeg_split, w_item), w_item

        futs = dict(start_all())
        n_jobs = len(futs)
        stats = wait_for_results(futs, verbose)

    print("Total jobs: {n}, Success: {success}, Errors: {error}".format(n=n_jobs, **stats))

    if stats["error"] > 0:
        print("WARNING: Due to errors, some chapters may not have been processed!",
              file=sys.stderr)
        return -1

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
                if verbose:
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
    """
    Split a single chapter using ffmpeg subprocess. Blocks until completion.

    w_item:
        a WorkItem that fully describes the task to be performed
    """

    # cmd is a a flat list of strings
    cmd = workitem_to_ffmpeg_cmd(w_item)

    try:
        proc = sub.run(cmd, check=True, stdout=sub.PIPE, stderr=sub.PIPE)
        return {'ok': True, 'w_item': w_item, 'proc': proc, 'exn': None, 'cmd': cmd}
    except sub.CalledProcessError as exn:
        return {'ok': False, 'w_item': w_item, 'proc': None, 'exn': exn, 'cmd': cmd}


if __name__ == '__main__':
    sys.exit(main(sys.argv))
