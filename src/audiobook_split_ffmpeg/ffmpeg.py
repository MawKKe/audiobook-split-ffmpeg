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
Utility functionality for interacting with system ffmpeg executables
"""

import json
import os
import subprocess as sub
import typing as t
from pathlib import Path

from .util import WorkItem, _validate_chapter, _sanitize_string, _get_title_maybe


def ffprobe_read_chapters(filename: Path) -> t.Dict[t.Any, t.Any]:
    """
    Read chapter metadata from 'filename' using ffprobe and return it as dict
    """

    command = [
        'ffprobe',
        '-i',
        str(filename),
        '-v',
        'error',
        '-print_format',
        'json',
        '-show_chapters',
    ]

    # ffmpeg & ffprobe write output into stderr, except when
    # using -show_XXXX and -print_format. Strange.
    # Had we ran ffmpeg instead of ffprobe, this would throw since ffmpeg without
    # an output file will exit with exitcode != 0
    proc = sub.run(
        command,
        check=True,
        stdout=sub.PIPE,
        stderr=sub.PIPE,
    )

    # .decode() will most likely explode if the ffprobe json output (chapter metadata)
    # was written with some weird encoding, and even more so if the data contains text in
    # multiple different text encodings...

    # TODO how does this handle non-ascii/utf8 metadata? # pylint: disable=fixme
    # https://stackoverflow.com/questions/10009753/python-dealing-with-mixed-encoding-files
    output = proc.stdout.decode('utf8')

    data = json.loads(output)

    return data


def workitem_to_ffmpeg_cmd(w_item: WorkItem) -> t.List[str]:
    """
    Build command list from WorkItem.
    The command list can be directly passed to subprocess.run() or similar.
    """

    # NOTE:
    # '-nostdin' param should prevent your terminal becoming all messed up
    # during the pool processing.  But if it does, you can fix it with 'reset'
    # and/or 'stty sane'.  If corruption still occurs, let me know (email is at
    # the top of the file).

    _, in_ext = os.path.splitext(w_item.infile)
    _, out_ext = os.path.splitext(w_item.outfile)

    base_cmd = [
        'ffmpeg',
        '-nostdin',
        '-i',
        w_item.infile,
        '-v',
        'error',
        '-map_chapters',
        '-1',
        '-vn'
    ]

    if in_ext.lower() == out_ext.lower():
        # Same format. No conversion needed. Copy the stream.
        base_cmd += [
            '-c',
            'copy'
        ]

    base_cmd += [
        '-ss',
        w_item.start,
        '-to',
        w_item.end,
        '-n',
    ]

    metadata_track = [
        '-metadata',
        'track={}/{}'.format(w_item.ch_num, w_item.ch_max),
    ]

    # TODO how does this handle mangled title values? # pylint: disable=fixme
    metadata_title = (
        [
            '-metadata',
            'title={}'.format(w_item.ch_title),
        ]
        if w_item.ch_title
        else []
    )

    # Build the final command
    cmd = base_cmd + metadata_track + metadata_title + [w_item.outfile]

    return cmd


def ffmpeg_split_chapter(w_item: WorkItem) -> t.Dict:
    """
    Split a single chapter using ffmpeg subprocess. Blocks until completion.

    w_item:
        a WorkItem that fully describes the task to be performed
    """

    # cmd is a a flat list of strings
    cmd = workitem_to_ffmpeg_cmd(w_item)

    _dir = os.path.dirname(w_item.outfile)
    if not os.path.isdir(_dir):
        os.makedirs(_dir, exist_ok=True)

    try:
        proc = sub.run(
            cmd,
            check=True,
            stdout=sub.PIPE,
            stderr=sub.PIPE,
        )
        return {
            'ok': True,
            'w_item': w_item,
            'proc': proc,
            'exn': None,
            'cmd': cmd,
        }
    except sub.CalledProcessError as exn:
        return {
            'ok': False,
            'w_item': w_item,
            'proc': None,
            'exn': exn,
            'cmd': cmd,
        }


def compute_workitems(
    infile: Path,
    outdir: t.Optional[Path] = None,
    enumerate_files: bool = True,
    use_title_in_filenames: bool = True,
    out_ext: t.Optional[str] = None
) -> t.Iterator[WorkItem]:
    """
    Compute WorkItem's for each chapter to be processed. These WorkItems can be then used
    for launching ffmpeg processes (see ffmpeg_split_chapter)

    Arguments:

    infile
        Path to an audio(book) file. Must contain chapter information in its metadata.
    outdir
        Path to a directory where chapter files will be written.
        If the value is `None`, a directory named `infile` (without an extension) will be used.
    enumerate_files
        Include chapter numbers in output filenames?
    use_title_in_filenames
        Include chapter titles in output filenames?
    out_ext
        A new file extension, in case conversion to another format is required.
        If `None`, the extension remains unchanged.
    """

    in_root, in_ext = os.path.splitext(os.path.basename(infile))

    if 0 in [len(in_root), len(in_ext)]:
        raise RuntimeError('Unexpected input filename format - root part or extension is empty')

    # Make sure extension has no leading dots.
    in_ext = in_ext[1:] if in_ext.startswith('.') else in_ext
    if out_ext:
        out_ext = out_ext[1:] if out_ext.startswith('.') else out_ext
    else:
        out_ext = in_ext

    if outdir is None:
        outdir, _ = os.path.splitext(infile)

    # Get chapter metadata
    info = ffprobe_read_chapters(infile)

    if (info is None) or ('chapters' not in info) or (len(info['chapters']) == 0):
        raise RuntimeError('Could not parse chapters')

    # Collect all valid chapters into a list
    chapters = list(
        filter(
            None,
            (_validate_chapter(ch) for ch in info['chapters']),
        )
    )

    # Find maximum chapter number. Remember + 1 since enumeration starts at zero!
    ch_max = max(chap['id'] + 1 for chap in chapters)

    # Produces equal-width zero-padded chapter numbers for use in filenames.
    def chnum_fmt(n: int) -> str:
        return '{n:{fill}{width}}'.format(n=n, fill='0', width=len(str(ch_max)))

    for chapter in chapters:
        # Get cleaned title or None
        title_maybe = _sanitize_string(_get_title_maybe(chapter))

        ch_num = chapter['id'] + 1

        # Use chapter title in output filename base unless disabled or not available.
        # Otherwise, use the root part of input filename
        title = title_maybe if (use_title_in_filenames and title_maybe) else in_root

        out_base = '{title}.{ext}'.format(title=title, ext=out_ext)

        # Prepend chapter number if requested
        if enumerate_files:
            out_base = '{0}. {1}'.format(chnum_fmt(ch_num), out_base)

        yield WorkItem(
            infile=infile,
            outfile=os.path.join(outdir, out_base),
            start=chapter['start_time'],
            end=chapter['end_time'],
            ch_num=ch_num,
            ch_max=ch_max,
            ch_title=_get_title_maybe(chapter),
        )
