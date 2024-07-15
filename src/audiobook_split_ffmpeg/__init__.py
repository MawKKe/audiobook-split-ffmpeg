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
Split audiobook file into per-chapter files using chapter metadata and ffmpeg


This package provides the functionality to split a single audiobook file into
several smaller chapter files, assuming the file has embedded chapter metadata
available.

This package can be used either as a standalone CLI application or as library.
The CLI application should be available as:

    $ audiobook-split-ffmpeg

...assuming this package installed with 'pip install' or similar.  Run the
script with --help to get started.

The package can be used as a library by importing the 'audiobook_split_ffmpeg' module
and using the provided functions. The functions are rudimentary, meaning some additional
housekeeping code may be needed. See the file 'audiobook_split_ffmpeg/cli.py' for an
example how to combine the functions to produce a useful application.

More information in Github: https://github.com/MawKKe/audiobook-split-ffmpeg
"""

from .ffmpeg import (
    ffprobe_read_chapters,
    workitem_to_ffmpeg_cmd,
    ffmpeg_split_chapter,
)
from .workers import process_workitems
from .util import compute_workitems

__all__ = [
    'ffprobe_read_chapters',
    'workitem_to_ffmpeg_cmd',
    'ffmpeg_split_chapter',
    'process_workitems',
    'compute_workitems',
]
__author__ = 'Markus Holmström (MawKKe) <markus@mawkke.fi>'
__version__ = '0.2.0'
