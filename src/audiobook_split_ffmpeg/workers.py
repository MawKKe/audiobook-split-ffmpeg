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
Functioality for consuming WorkItems and producing final chapter files
with parallel worker threads/processes.
"""

import os
import sys
from concurrent.futures import (
    ThreadPoolExecutor,
    as_completed,
)

from .ffmpeg import ffmpeg_split_chapter


def process_workitems(
    work_items,
    outdir,
    concurrency=1,
    verbose=False,
):
    """
    Runs ffmpeg worker process for each WorkItem, parallellized with ThreadPoolExecutor
    """

    os.makedirs(outdir, exist_ok=True)

    if verbose:
        print('Output directory: {}'.format(outdir))
        print('Starting ThreadPoolExecutor with concurrency={0}'.format(concurrency))

    n_jobs = 0
    with ThreadPoolExecutor(max_workers=concurrency) as pool:

        def start_all():
            for w_item in work_items:
                if verbose:
                    print('Submitting job: {}'.format(w_item))
                yield (
                    pool.submit(
                        ffmpeg_split_chapter,
                        w_item,
                    ),
                    w_item,
                )

        futs = dict(start_all())
        n_jobs = len(futs)
        stats = _wait_for_results(futs, verbose)

    print('Total jobs: {n}, Success: {success}, Errors: {error}'.format(n=n_jobs, **stats))

    if stats['error'] > 0:
        print(
            'WARNING: Due to errors, some chapters may not have been processed!',
            file=sys.stderr,
        )
        return -1

    return 0


def _wait_for_results(futs, verbose=False):
    """
    Collect ffmpeg processing results and display whether chapter was processed correctly
    """
    stats = {'success': 0, 'error': 0}
    for fut in as_completed(futs):
        w_item = futs[fut]
        try:
            result = fut.result()
        # this looks nasty as hell, but hey, this is what they do in python docs..
        except Exception as exn_wtf:  # pylint: disable=broad-except
            stats['error'] += 1
            print("ERROR: job '{}' generated an exeption: {}".format(w_item.outfile, exn_wtf))
        else:
            if result['ok']:
                stats['success'] += 1
                if verbose:
                    print('SUCCESS: {0}'.format(w_item.outfile))
            else:
                stats['error'] += 1
                exn_proc = result['exn']
                print('FAILURE: {0}'.format(exn_proc.stderr.decode('utf8').strip()))
                if verbose:
                    print('Command that failed: {0}'.format(result['cmd']))
                    print('-' * 5)
    return stats
