from setuptools import setup, find_packages

setup(
    name="ytknow",
    version="1.2.0",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    install_requires=[
        "yt-dlp",
        "colorama",
        "openai",
        "openai-whisper"
    ],
    entry_points={
        "console_scripts": [
            "ytknow=ytknow.cli:main",
        ],
    },
    python_requires=">=3.8",
)
