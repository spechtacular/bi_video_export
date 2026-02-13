from setuptools import setup, find_packages

setup(
    name="bi-exporter",
    version="1.0.0",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    install_requires=[
        "requests>=2.31.0",
        "PyYAML>=6.0",
    ],
    entry_points={
        "console_scripts": [
            "bi-export=bi_exporter.bi_interface:main",
        ],
    },
)

