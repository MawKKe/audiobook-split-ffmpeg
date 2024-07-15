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
Various utilities for audiobook_split_ffmpeg
"""

import os
from collections import namedtuple
import typing as t
from pathlib import Path

from .ffmpeg import ffprobe_read_chapters

# Helper type for collecting necessary information about chapter for processing
WorkItem = namedtuple(
    'WorkItem',
    [
        'infile',
        'outfile',
        'start',
        'end',
        'ch_num',
        'ch_max',
        'ch_title',
    ],
)


# Special characters interpreted specially by most crappy software

_CHR_BLACKLIST = [
    '\\',
    '/',
    ':',
    '*',
    '?',
    '"',
    '<',
    '>',
    '|',
    '\0',
]


def _sanitize_string(original: t.Optional[str]) -> t.Optional[str]:
    """
    Filter typical special letters from string
    """
    if original is None:
        return None
    return ''.join(c for c in original if c not in _CHR_BLACKLIST)


Chapter = t.Dict[str, t.Any]


def _validate_chapter(chap: Chapter) -> t.Optional[Chapter]:
    """
    Checks that chapter is valid (i.e has valid length)
    """
    start = chap['start']
    end = chap['end']
    if (end - start) <= 0:
        msg = 'WARNING: chapter {0} duration <= 0 (start: {1}, end: {2}), skipping...'
        print(msg.format(chap['id'], start, end))
        return None
    return chap


def _get_title_maybe(chap: Chapter) -> t.Optional[str]:
    """
    Chapter to title (string) or None
    """
    if 'tags' not in chap:
        return None
    return chap['tags'].get('title', None)


def compute_workitems(
    infile: Path, outdir: Path, enumerate_files: bool = True, use_title_in_filenames: bool = True
) -> t.Iterator[WorkItem]:
    """
    Compute WorkItem's for each chapter to be processed. These WorkItems can be then used
    for launching ffmpeg processes (see ffmpeg_split_chapter)

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
        raise RuntimeError('Unexpected input filename format - root part or extension is empty')

    # Make sure extension has no leading dots.
    in_ext = in_ext[1:] if in_ext.startswith('.') else in_ext

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

        out_base = '{title}.{ext}'.format(title=title, ext=in_ext)

        # Prepend chapter number if requested
        if enumerate_files:
            out_base = '{0} - {1}'.format(chnum_fmt(ch_num), out_base)

        yield WorkItem(
            infile=infile,
            outfile=os.path.join(outdir, out_base),
            start=chapter['start_time'],
            end=chapter['end_time'],
            ch_num=ch_num,
            ch_max=ch_max,
            ch_title=_get_title_maybe(chapter),
        )
