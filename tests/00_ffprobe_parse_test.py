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

import pytest

here = Path(__file__).resolve().parent

def test_file_with_chapters():
    chapters = ffprobe_read_chapters(beep['file'])
    assert chapters == beep['expected_chapters']


def test_file_without_chapters():
    chapters = ffprobe_read_chapters(beep_nochap['file'])
    assert chapters == beep_nochap['expected_chapters']


def _internal_drop_key(data: t.Dict[t.Any, t.Any], key: t.Any) -> t.Dict[t.Any, t.Any]:
    return {k: v for k, v in data.items() if k != key}

def test_internal_drop_key():
    assert _internal_drop_key({'a': 1, 'b': 2, 'c': 3}, 'b') == {'a': 1, 'c': 3}


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

@pytest.fixture(scope='session')
def valid_chapter_dict() -> t.Dict[str, t.Any]:
    return json.loads("""
    {
        "id": 1,
        "time_base": "1/1000",
        "start": 20000,
        "start_time": "29.123456",
        "end": 40000,
        "end_time": "49.654321",
        "tags": {
            "title": "All You Can BEEP Buffee"
        }
    }
    """)

def test__parse_chapter_dict__accepts_valid_entry(valid_chapter_dict):
    chap = ffprobe.parse_chapter_dict(valid_chapter_dict)
    assert isinstance(chap, ffprobe.Chapter)
    assert chap.id == 1
    assert chap.start_time == '29.123456'
    assert chap.end_time == '49.654321'
    assert 'title' in chap.tags and chap.tags['title'] == 'All You Can BEEP Buffee'

def test__parse_chapter_dict__rejects_invalid_entry(valid_chapter_dict):
    # Any of the required keys causes rejection of the entry
    with pytest.raises(ffprobe.FFProbeError):
        _ = ffprobe.parse_chapter_dict(_internal_drop_key(valid_chapter_dict, 'id'))
    with pytest.raises(ffprobe.FFProbeError):
        _ = ffprobe.parse_chapter_dict(_internal_drop_key(valid_chapter_dict, 'start_time'))
    with pytest.raises(ffprobe.FFProbeError):
        _ = ffprobe.parse_chapter_dict(_internal_drop_key(valid_chapter_dict, 'end_time'))

def test_parse_metadata():
    meta = ffprobe.parse_metadata(_raw_ffprobe_metadata_json)
    assert len(meta.chapters) == 3
    expect_chapters = [
        ffprobe.Chapter(
            id=0,
            start_time='0.000000',
            end_time='20.000000',
            tags={'title': 'It All Started With a Simple BEEP'},
        ),
        ffprobe.Chapter(
            id=1,
            start_time='20.000000',
            end_time='40.000000',
            tags={'title': 'All You Can BEEP Buffee'},
        ),
        ffprobe.Chapter(
            id=2,
            start_time='40.000000',
            end_time='60.000000',
            tags={'title': 'The Final Beep'},
        ),
    ]
    assert meta.chapters == expect_chapters


def test_parse_metadata_should_not_crash_when_chapters_are_missing():
    meta1 = ffprobe.parse_metadata('{}')  # ok
    assert len(meta1.chapters) == 0
    meta2 = ffprobe.parse_metadata('{"chapters": []}')
    assert len(meta2.chapters) == 0


def test_parse_metadata_raises_when_unexpected_or_incomplete_chapter_entry_encountered():
    with pytest.raises(ffprobe.FFProbeError):
        _ = ffprobe.parse_metadata('{"chapters": [{"id": 0, "rest-are-missing": true}]}')


def test_ffprobe():
    content = ffprobe.ffprobe(here / 'beep.m4a')
    assert len(content) > 0
    res = json.loads(content)
    assert isinstance(res, dict)


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


def _internal_find_matching_pairs(
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
        '-y',
        '-metadata',
        'title=All You Can BEEP Buffee',
        '-metadata',
        'track=2/3',
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

    pairs = list(_internal_find_matching_pairs(cmd, '-metadata', 'track=*'))
    assert len(pairs) == 1
    assert pairs[0] == ('-metadata', 'track=2/3')

    pairs = list(_internal_find_matching_pairs(cmd, '-metadata', 'title=*'))
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


def test_new_main(tmpdir):
    args = ['pytest-main', '-i', str(here/ 'beep.m4a'), '-o', str(tmpdir)]
    res = cli_new.inner_main(args)
    assert res == 0

    with pytest.raises(SystemExit):
        # help should be printed
        args = ['pytest-main', '-h']
        assert cli_new.inner_main(args) != 0

    with pytest.raises(SystemExit):
        # missing argument '-i'
        args = ['pytest-main', '-o', 'foo']
        assert cli_new.inner_main(args) != 0

    with pytest.raises(SystemExit):
        # missing argument '-o'
        args = ['pytest-main', '-i', 'bar.m4a']
        assert cli_new.inner_main(args) != 0
