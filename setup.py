from setuptools import setup, find_packages

setup(
    name='clockiPy',
    version='0.1.0',
    description='A CLI tool for fetching and displaying Clockify time entries in a clean table.',
    author='René Lachmann',
    packages=find_packages(),
    install_requires=[
        'requests',
        'tabulate',
        'python-dotenv',
        'markdown',
    ],
    entry_points={
        'console_scripts': [
            'clockipy=clockify_cli:main',
        ],
    },
    include_package_data=True,
    package_data={
        '': ['clockipy.env.example'],
    },
    python_requires='>=3.7',
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
) 