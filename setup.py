from setuptools import setup, find_packages

setup(
    name='riffusion_api',
    version='0.41',
    packages=find_packages(),
    install_requires=[
        'requests~=2.31.0',
        'pydub~=0.25.1'
    ],
)
