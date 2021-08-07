# audiobook-split-ffmpeg.py

Split audiobook file into per-chapter files using chapter metadata and ffmpeg.

Useful in situations where your preferred audio player does not support chapter metadata.

**NOTE**: Works only if the input file actually has chapter metadata (see example below)

# Example

Let's say, you have an audio file `mybook.m4b`, for which `ffprobe -i mybook.m4b`
shows the following:

    Chapter #0:0: start 0.000000, end 1079.000000
    Metadata:
      title           : Chapter Zero
    Chapter #0:1: start 1079.000000, end 2040.000000
    Metadata:
      title           : Chapter One
    Chapter #0:2: start 2040.000000, end 2878.000000
    Metadata:
      title           : Chapter Two
    Chapter #0:3: start 2878.000000, end 3506.000000

Then, running:

    $ python3 audiobook-split-ffmpeg.py --infile mybook.m4b --outdir /tmp/foo

..produces the following files:
- /tmp/foo/ch 000 Chapter Zero.m4b
- /tmp/foo/ch 001 Chapter One.m4b
- /tmp/foo/ch 002 Chapter Two.m4b

You may then play these files with your preferred application.

# Usage

See the help:

    $ python3 audiobook-split-ffmpeg.py -h

In the simplest case you can just call

    $ python3 audiobook-split-ffmpeg.py --infile /path/to/audio.m4b

By default, the chapter files will be written into a temporary directory under
`/tmp`. You may specify alternative output directory with `--outdir <path>`,
which will be created if it does not exist. Note that this script will never
overwrite files, so you must delete conflicting files manually (or specify some
other empty/nonexistent directory)

The chapter titles will be included in the filenames if they are available in
the chapter metadata. You may prevent this behaviour with flag `--no-use-title-as-filename`,
in which case the filenames will include the input file basename instead (this
is useful is your metadata is crappy or malformed, for example).

You may specify how many parallel `ffmpeg` jobs you want with command line param `--concurrency`.
The default concurrency is equal to the number of cores available. Note that at some point increasing
the concurrency might not increase the throughput. (We specifically instruct `ffmpeg` to NOT perform
re-encoding, so most of the processing work consists of copying the existing encoded audio data from the
input file to the output file(s) - this kind of processing is more I/O bounded than CPU-bounded).

# Dependencies

- Python 3.5 or newer
- Obviously you need ffmpeg (and ffprobe) installed.

There are no 3rd party library dependencies. Everything is accomplished with just the python3 stdlib.

# Features

- The script does not transcode/re-encode the audio data. This speeds up the processing, but has
  the possibility of creating mangled audio in some rare cases (let me know if this happens).

- This script will instruct ffmpeg to write metadata in the resulting chapter files, including:
  - `track`: the chapter number; in the format X/Y, where X = chapter number, Y = total num of chapters.
  - `title`: the chapter title, as-is (if available)

- The chapter numbers are included in the output file names, padded with zeroes so that all
  numbers are of equal length. This makes the files much easier to sort by name.

- The work is parallelized to speed up the processing.

# Licese

Copyright 2018 Markus Holmström (MawKKe)

The works under this repository are licenced under Apache License 2.0.
See file `LICENCE` for more information.

# Contributing

This project is hosted at https://github.com/MawKKe/audiobook-split-ffmpeg

You are welcome to leave bug reports, fixes and feature requests. Thanks!

