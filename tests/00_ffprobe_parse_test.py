import json
from pathlib import Path
import typing as t
import fnmatch
from itertools import product
import shlex

from audiobook_split_ffmpeg import (
    ffprobe_read_chapters,
    ffprobe,
)

from audiobook_split_ffmpeg.model import Chapter

from .testdata import beep, beep_nochap


def test_file_with_chapters():
    chapters = ffprobe_read_chapters(beep['file'])
    assert chapters == beep['expected_chapters']


def test_file_without_chapters():
    chapters = ffprobe_read_chapters(beep_nochap['file'])
    assert chapters == beep_nochap['expected_chapters']


_raw_ffprobe_metadata_json = """
{
    "chapters": [
        {
            "id": 0,
            "time_base": "1/1000",
            "start": 0,
            "start_time": "0.000000",
            "end": 20000,
            "end_time": "20.000000",
            "tags": {
                "title": "It All Started With a Simple BEEP"
            }
        },
        {
            "id": 1,
            "time_base": "1/1000",
            "start": 20000,
            "start_time": "20.000000",
            "end": 40000,
            "end_time": "40.000000",
            "tags": {
                "title": "All You Can BEEP Buffee"
            }
        },
        {
            "id": 2,
            "time_base": "1/1000",
            "start": 40000,
            "start_time": "40.000000",
            "end": 60000,
            "end_time": "60.000000",
            "tags": {
                "title": "The Final Beep"
            }
        }
    ]
}
"""

here = Path(__file__).resolve().parent


def test_ffprobe():
    content = ffprobe.ffprobe(here / 'beep.m4a')
    assert len(content) > 0
    res = json.loads(content)
    assert isinstance(res, dict)


def test_parse_metadata():
    meta = ffprobe.parse_metadata(_raw_ffprobe_metadata_json)
    assert len(meta.chapters) == 3
    expect_chapters = [
        ffprobe.Chapter(
            id=0,
            start=0,
            start_time='0.000000',
            end=20000,
            end_time='20.000000',
            time_base=(1, 1000),
            tags={'title': 'It All Started With a Simple BEEP'},
        ),
        ffprobe.Chapter(
            id=1,
            start=20000,
            start_time='20.000000',
            end=40000,
            end_time='40.000000',
            time_base=(1, 1000),
            tags={'title': 'All You Can BEEP Buffee'},
        ),
        ffprobe.Chapter(
            id=2,
            start=40000,
            start_time='40.000000',
            end=60000,
            end_time='60.000000',
            time_base=(1, 1000),
            tags={'title': 'The Final Beep'},
        ),
    ]
    assert meta.chapters == expect_chapters


import pytest


def test_parse_metadata_should_not_crash_when_chapters_are_missing():
    meta1 = ffprobe.parse_metadata('{}')  # ok
    assert len(meta1.chapters) == 0
    meta2 = ffprobe.parse_metadata('{"chapters": []}')
    assert len(meta2.chapters) == 0


def test_parse_metadata_raises_when_unexpected_or_incomplete_chapter_entry_encountered():
    with pytest.raises(ffprobe.FFProbeError):
        _ = ffprobe.parse_metadata('{"chapters": [{"id": 0, "rest-are-missing": true}]}')


def test_read_fileinfo():
    info = ffprobe.read_fileinfo(here / 'beep.m4a')
    assert len(info.meta.chapters) == 3
    assert info.path == here / 'beep.m4a'


def test_chapter_num_format_padded():
    assert ffprobe.num_format_padded(0, 1) == '0'
    assert ffprobe.num_format_padded(1, 2) == '01'
    assert ffprobe.num_format_padded(2, 3) == '002'
    assert ffprobe.num_format_padded(69, 3) == '069'
    assert ffprobe.num_format_padded(1234, 3) == '1234'


def find_matching_pairs(
    haystack: t.List[str], first: str, second: str
) -> t.Iterator[t.Tuple[str, str]]:
    """
    scan list for pair of elements matching 'first' and 'second' (that are possibly globs),
    yield all matching pairs
    """
    for a, b in zip(haystack, haystack[1:]):
        if fnmatch.fnmatch(a, first) and fnmatch.fnmatch(b, second):
            yield (a, b)


@pytest.fixture(scope='session')
def beep_info():
    return ffprobe.read_fileinfo(here / 'beep.m4a')


def test_make_ffmpeg_cmd(beep_info):
    opts = ffprobe.Options()
    cmd = ffprobe.make_ffmpeg_split_cmd(beep_info, beep_info.meta.chapters[1], Path('myout'), opts)
    expect = [
        'ffmpeg',
        '-nostdin',
        '-i',
        str((here / 'beep.m4a').resolve()),
        '-v',
        'error',
        '-map_chapters',
        '-1',
        '-vn',
        '-c',
        'copy',
        '-ss',
        '20.000000',
        '-to',
        '40.000000',
        '-n',
        '-metadata',
        'track=2/3',
        '-metadata',
        'title=All You Can BEEP Buffee',
        'myout/2 - All You Can BEEP Buffee.m4a',
    ]
    assert cmd == expect


def test_make_ffmpeg_split_cmd__no_use_title_in_name(beep_info):
    opts = ffprobe.Options()
    opts.use_title_in_name = False
    cmd = ffprobe.make_ffmpeg_split_cmd(beep_info, beep_info.meta.chapters[1], Path('myout'), opts)
    expect = 'myout/2 - beep.m4a'
    assert cmd[-1] == expect


def test_make_ffmpeg_split_cmd__enumeration_offset(beep_info):
    opts = ffprobe.Options()
    opts.track_enumeration_offset = 5
    cmd = ffprobe.make_ffmpeg_split_cmd(beep_info, beep_info.meta.chapters[1], Path('myout'), opts)
    expect = 'myout/6 - All You Can BEEP Buffee.m4a'
    assert cmd[-1] == expect


def test_make_ffmpeg_split_cmd__metadata_handling(beep_info):
    opts = ffprobe.Options(use_title_in_meta=False)
    cmd = ffprobe.make_ffmpeg_split_cmd(beep_info, beep_info.meta.chapters[1], Path('myout'), opts)

    # output filename should not change
    assert cmd[-1] == 'myout/2 - All You Can BEEP Buffee.m4a'

    pairs = list(find_matching_pairs(cmd, '-metadata', 'track=*'))
    assert len(pairs) == 1
    assert pairs[0] == ('-metadata', 'track=2/3')

    pairs = list(find_matching_pairs(cmd, '-metadata', 'title=*'))
    assert len(pairs) == 0


def test_split_options_combinations(beep_info):
    results = set()
    for a, b, c in product([False, True], [False, True], [False, True]):
        opts = ffprobe.Options(use_title_in_name=a, use_title_in_meta=b, use_track_num_in_meta=c)

        for ch in beep_info.meta.chapters:
            cmd = ffprobe.make_ffmpeg_split_cmd(beep_info, ch, Path('myout'), opts)
            results.add(shlex.join(cmd))

    # We don't really care what the values of individual results (ffmpeg cmdlines) are,
    # we care that they are distinct between the option combinations
    assert len(results) == 24
