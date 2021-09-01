from setuptools import setup, find_packages
import pkg_resources
import pathlib

here = pathlib.Path(__file__).parent.resolve()

long_description = (here / 'README.md').read_text(encoding='utf-8')

requirements = []

if __name__ == "__main__":
    setup(
            name="audiobook-split-ffmpeg",
            version='0.1.0',
            description='Split audiobook file into per-chapter files using chapter metadata and ffmpeg',
            long_description=long_description,
            long_description_content_type='text/markdown',
            url='https://github.com/MawKKe/audiobook-split-ffmpeg',
            author='Markus H (MawKKe)',
            author_email='markus@mawkke.fi',
            package_dir={'': 'src'},
            packages=find_packages(where='src'),
            entry_points={
                'console_scripts': {
                    'audiobook-split-ffmpeg=audiobook_split_ffmpeg.cli:main'
                }
            },
            python_requires='>=3.6, <4',
            install_requires=requirements,
            extras_require={
                'dev': [
                    'pytest'
                ]
            },
            project_urls={
                'Bug reports': 'https://github.com/MawKKe/audiobook-split-ffmpeg/issues',
                'Source': 'https://github.com/MawKKe/audiobook-split-ffmpeg'
            },
    )
