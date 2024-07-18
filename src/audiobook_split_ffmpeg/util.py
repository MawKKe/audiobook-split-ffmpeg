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

import typing as t

from . import model


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


def _validate_chapter(chap: model.Chapter) -> t.Optional[model.Chapter]:
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


def _get_title_maybe(chap: model.Chapter) -> t.Optional[str]:
    """
    Chapter to title (string) or None
    """
    if 'tags' not in chap:
        return None
    return t.cast(t.Dict[str, str], chap['tags']).get('title', None)
