from audiobook_split_ffmpeg import (
    workitem_to_ffmpeg_cmd,
)
from audiobook_split_ffmpeg.model import (
    WorkItem,
)


def test_workitem_to_ffmpeg_cmd():
    wi = WorkItem(
        infile='koe.m4a',
        outfile='out/Output File.m4a',
        start='13.1230',
        end='42.5363',
        ch_num=2,
        ch_max=3,
        ch_title='Output title',
    )

    cmd = workitem_to_ffmpeg_cmd(wi)

    expected = [
        'ffmpeg',
        '-nostdin',
        '-i',
        'koe.m4a',
        '-v',
        'error',
        '-map_chapters',
        '-1',
        '-vn',
        '-c',
        'copy',
        '-ss',
        '13.1230',
        '-to',
        '42.5363',
        '-n',
        '-metadata',
        'track=2/3',
        '-metadata',
        'title=Output title',
        'out/Output File.m4a',
    ]

    assert len(cmd) > 1
    assert len(cmd) == len(expected)
    assert cmd == expected
