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
import re
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

def parseChapters(filename):
    command = [ "ffprobe", '-i', filename, "-v", "error", "-print_format", "json", "-show_chapters"]
    try:
        # ffmpeg & ffprobe write output into stderr, except when
        # using -show_XXXX and -print_format. Strange.
        p = sub.run(command, stdout=sub.PIPE, stderr=sub.PIPE)

        # had we ran ffmpeg instead of ffprobe, this would throw since ffmpeg without
        # an output file will exit with exitcode != 0
        p.check_returncode()

        # .decode() will most likely explode if the ffprobe json output (chapter metadata)
        # was written with some weird encoding, and even more so if the data contains text in
        # multiple different text encodings...

        # TODO?
        # https://stackoverflow.com/questions/10009753/python-dealing-with-mixed-encoding-files
        output = p.stdout.decode('utf8')

        d = json.loads(output)

        return d
    except sub.CalledProcessError as e:
        print("ERROR: ", e)
        print("FFPROBE-STDOUT: ", p.stdout)
        print("FFPROBE-STDERR: ", p.stderr)
        return None


# Helper type for collecting necessary information about chapter for processing
WorkItem = namedtuple("WorkItem", ["infile", "outfile", "start", "end", "ch_id", "ch_max", "ch_title"])

# Build command list from WorkItem. The command list can be directly passed to subprocess.run() or similar.
def workitem_to_ffmpeg_cmd(wi):
    # NOTE:
    # '-nostdin' param should prevent your terminal becoming all messed up during the pool processing.
    # But if it does, you can fix it with 'reset' and/or 'stty sane'.
    # If corruption still occurs, let me know (email is at the top of the file).

    base_cmd = [
        "ffmpeg",
        "-nostdin",
        "-i", wi.infile,
        "-v", "error",
        "-map_chapters", "-1",
        "-vn",
        "-c", "copy",
        "-ss", wi.start,
        "-to", wi.end,
        "-n"
    ]

    metadata_track = ["-metadata", "track={}/{}".format(wi.ch_id, wi.ch_max)]

    # TODO how does this handle mangled title values?
    metadata_title = ["-metadata", "title={}".format(wi.ch_title)] if wi.ch_title else []

    # Build the final command
    cmd = base_cmd + metadata_track + metadata_title + [wi.outfile]

    return cmd

def main(argv):
    p = argparse.ArgumentParser()
    p.add_argument("--verbose", required=False, action="store_true", help="Show more output")
    p.add_argument("--infile", required=True, help="Input file")
    p.add_argument("--concurrency", required=False, default=cpu_count(), help="Number of concurrent processes", type=int)
    p.add_argument("--dry-run", required=False, action='store_true', help="Show actions, do not actually split file")
    p.add_argument("--no-use-title", "--no-use-title-as-filename", required=False, dest='use_title', action='store_false',
            help="Prevent including chapter title in the filenames (in case it is garbage)")
    p.add_argument("--outdir", required=False,
            help="Output directory. If omitted, files are written into a new /tmp/ffmpeg-split-XXX directory.")

    args = p.parse_args(argv[1:])

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

    info = parseChapters(args.infile)

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

    def validate_chapter(ch):
        start = ch['start']
        end   = ch['end']
        if (end - start) <= 0:
            print("WARNING: chapter {0} duration is zero or negative (start: {1}, end: {2}), skipping...".format(ch['id'], start, end))
            return None
        return ch

    # Collect all valid chapters into a list
    chapters = list(filter(None, (validate_chapter(ch) for ch in info["chapters"])))

    # Find maximum chapter number
    max_chapter = max(ch['id'] for ch in chapters)

    # Produce equal-width zero-padded chapter numbers for use in filenames; makes sorting easier
    chnum_format = lambda n: '{n:{fill}{width}}'.format(n=n, fill='0', width=len(str(max_chapter)))

    # Compute output filename for chapter 'n' with 'title'.
    def outfile_basename(n, title_maybe):
        fmt = "ch {ch_num} - {title}.{ext}"
        ch_num = chnum_format(n)
        if args.use_title and title_maybe:
            return fmt.format(ch_num=ch_num, title=title_maybe, ext=fext)
        return fmt.format(ch_num=ch_num, title=fbase, ext=fext)

    # Chapter to title (string) or None
    def get_title_maybe(ch):
        if "tags" not in ch:
            return None
        return ch["tags"].get("title", None)

    def gen_workitems():
        for chapter in chapters:
            out_base = outfile_basename(chapter["id"], get_title_maybe(chapter))
            yield WorkItem(
                infile   = args.infile,
                outfile  = os.path.join(outdir, out_base),
                start    = chapter["start_time"],
                end      = chapter["end_time"],
                ch_id    = chapter["id"],
                ch_max   = max_chapter,
                ch_title = get_title_maybe(chapter)
            )

    # WIS = WorkItemS
    WIS = list(gen_workitems())

    # FIXME: dry-run usually means "no side-effects". However, this
    # script will create the output directory in all cases.
    if args.dry_run:
        print("Dry run enabled. These commands would be run by workers:")
        print("---")
        for cmd in (workitem_to_ffmpeg_cmd(wi) for wi in WIS):
            print(cmd)
        print("---")
        print("Dry run complete. Exiting...")
        return 0

    print("Total: {0} chapters, concurrency: {1}".format(len(WIS), args.concurrency))

    n_jobs = 0
    errors = 0
    success = 0
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        def start_all():
            for wi in WIS:
                if args.verbose:
                    print("Submitting job: {}".format(wi))
                yield pool.submit(ffmpeg_split, wi), wi

        futs = dict(start_all())

        n_jobs = len(futs)

        for fut in as_completed(futs):
            try:
                result = fut.result()
            # this looks nasty as hell, but hey, this is what they do in python docs..
            except Exception as e:
                errors += 1
                print("ERROR: job '{}' generated an exeption: {}".format(futs[fut].outfile, e))
            else:
                work_item = result["wi"]
                if result['ok']:
                    success += 1
                    print("'{0}' - done".format(work_item.outfile))
                else:
                    errors += 1
                    proc = result["proc"]
                    print("FAILURE: {0}".format(work_item.outfile))
                    print("Command: {0}".format(result["cmd"]))
                    print("FFMPEG-STDOUT:", proc.stdout)
                    print("FFMPEG-STDERR:", proc.stderr)
                    print("-" * 20)


    print("---")
    print("Processing done. Total jobs: {}, Success: {}, Errors: {}".format(n_jobs, success, errors))
    if(errors > 0):
        print("WARNING: there were errors. Some chapters may not have been processed correctly!")

    print("Output directory:", outdir)
    return 0


def ffmpeg_split(wi):

    cmd = workitem_to_ffmpeg_cmd(wi)

    s = sub.run(cmd, stdout=sub.PIPE, stderr=sub.PIPE)

    try:
        s.check_returncode()
        return {'ok': True,  'wi': wi, 'proc': s, 'cmd': cmd}
    except sub.CalledProcessError as e:
        return {'ok': False, 'wi': wi, 'proc': e, 'cmd': cmd}


if __name__ == '__main__':
    sys.exit(main(sys.argv))
