import io

from setuptools import setup

with io.open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name='semantic-model',
    author='Melvin Bijman',
    author_email='bijman.m.m@gmail.com',

    description='All data about data in one model',
    long_description=long_description,
    long_description_content_type='text/markdown',

    version='2.1.0',
    py_modules=['semantic_model', 'one_to_one', 'data'],
    install_requires=['settipy'],
    include_package_data=True,
    license='MIT',

    url='https://github.com/Attumm/semantic-model',

    classifiers=[
        'Development Status :: 5 - Production/Stable',

        'Intended Audience :: Developers',

        'License :: OSI Approved :: MIT License',

        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
    ],
)
