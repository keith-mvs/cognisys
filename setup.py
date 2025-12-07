"""Setup script for CogniSys."""

from setuptools import setup, find_packages
from pathlib import Path

# Read README
readme_file = Path(__file__).parent / 'README.md'
long_description = readme_file.read_text(encoding='utf-8') if readme_file.exists() else ''

setup(
    name='cognisys',
    version='1.0.0',
    description='CogniSys - Intelligent File Management and Organization System',
    long_description=long_description,
    long_description_content_type='text/markdown',
    author='CogniSys Team',
    python_requires='>=3.10',
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'click>=8.0.0',
        'PyYAML>=6.0',
        'python-Levenshtein>=0.20.0',
    ],
    extras_require={
        'dev': [
            'pytest>=7.0.0',
            'pytest-cov>=4.0.0',
        ],
        'full': [
            'imagehash>=4.3.0',
            'Pillow>=10.0.0',
            'matplotlib>=3.5.0',
            'pandas>=2.0.0',
        ],
    },
    entry_points={
        'console_scripts': [
            'cognisys=cognisys.cli:main',
        ],
    },
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: End Users/Desktop',
        'Intended Audience :: System Administrators',
        'Topic :: System :: Filesystems',
        'Topic :: Utilities',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
    ],
)
