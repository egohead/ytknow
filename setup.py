from setuptools import setup, find_packages

setup(
    name="ytknow",
    version="1.3.0",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    install_requires=[
        "yt-dlp",
        "colorama",
        "openai",
        "openai-whisper",
        "typer",
        "pandas",
        "openpyxl",
        "tqdm",
        "pyyaml"
    ],
    entry_points={
        "console_scripts": [
            "ytknow=ytknow.cli:main",
            "yt-comments=ytknow.comments:app",
        ],
    },
    python_requires=">=3.8",
)
