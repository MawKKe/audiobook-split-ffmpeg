from collections import namedtuple
import typing as t

Chapter = t.Dict[str, t.Any]

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
