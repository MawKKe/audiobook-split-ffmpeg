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
import subprocess as sub
import typing as t
from pathlib import Path

from audiobook_split_ffmpeg.util import WorkItem

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

    base_cmd = [
        'ffmpeg',
        '-nostdin',
        '-i',
        w_item.infile,
        '-v',
        'error',
        '-map_chapters',
        '-1',
        '-vn',
        '-c',
        'copy',
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
