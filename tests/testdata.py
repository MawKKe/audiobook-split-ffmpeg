import pathlib

from audiobook_split_ffmpeg.util import WorkItem

here = pathlib.Path(__file__).parent.resolve()


beep = {
    'file': (here / 'beep.m4a'),
    'expected_chapters': {
        'chapters': [
            {
                'end': 20000,
                'end_time': '20.000000',
                'id': 0,
                'start': 0,
                'start_time': '0.000000',
                'tags': {'title': 'It All Started With a Simple BEEP'},
                'time_base': '1/1000',
            },
            {
                'end': 40000,
                'end_time': '40.000000',
                'id': 1,
                'start': 20000,
                'start_time': '20.000000',
                'tags': {'title': 'All You Can BEEP Buffee'},
                'time_base': '1/1000',
            },
            {
                'end': 60000,
                'end_time': '60.000000',
                'id': 2,
                'start': 40000,
                'start_time': '40.000000',
                'tags': {'title': 'The Final Beep'},
                'time_base': '1/1000',
            },
        ]
    },
    'expected_workitems': [
        WorkItem(
            infile=(here / 'beep.m4a'),
            outfile='foo/1 - It All Started With a Simple BEEP.m4a',
            start='0.000000',
            end='20.000000',
            ch_num=1,
            ch_max=3,
            ch_title='It All Started With a Simple BEEP',
        ),
        WorkItem(
            infile=(here / 'beep.m4a'),
            outfile='foo/2 - All You Can BEEP Buffee.m4a',
            start='20.000000',
            end='40.000000',
            ch_num=2,
            ch_max=3,
            ch_title='All You Can BEEP Buffee',
        ),
        WorkItem(
            infile=(here / 'beep.m4a'),
            outfile='foo/3 - The Final Beep.m4a',
            start='40.000000',
            end='60.000000',
            ch_num=3,
            ch_max=3,
            ch_title='The Final Beep',
        ),
    ],
}

beep_nochap = {
    'file': (here / 'beep-nochap.m4a'),
    'expected_chapters': {'chapters': []},
}
