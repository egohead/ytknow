# 📥 ytknow

<p align="center">
  <img src="ytknow_preview.png" alt="ytknow logo" width="400">
</p>

<p align="center">
  <img src="ytknow_terminal.png" alt="ytknow terminal screenshot" width="600">
</p>

**Extract YouTube channel knowledge into clean text files for learning & research.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.7+](https://img.shields.io/badge/python-3.7+-blue.svg)](https://www.python.org/downloads/)
[![yt-dlp](https://img.shields.io/badge/engine-yt--dlp-red.svg)](https://github.com/yt-dlp/yt-dlp)

---

## 📖 Table of Contents
- [⚖️ Legal Notice & Disclaimer](#⚖️-legal-notice--disclaimer)
- [✨ Features](#-features)
- [🤖 RAG & LLM Readiness](#-rag--llm-readiness)
- [🧠 How it Works](#-how-it-works-smart-deduplication)
- [🧹 Before & After](#-before--after)
- [🛠️ Built With](#️-built-with)
- [🛠️ Installation](#️-installation)
- [🚀 Usage](#-usage)
- [❓ FAQ](#-faq)
- [🤝 Contributing](#-contributing)

---

## ⚖️ Legal Notice & Disclaimer

**This tool is for:**
- ✅ Personal, non-commercial use
- ✅ Fair use, education, research  
- ✅ Offline learning & knowledge extraction
- ✅ Archiving your own content

**YouTube Terms of Service allow:**
- Downloading your own videos
- Offline viewing for personal use
- Subtitle extraction for accessibility

**DO NOT:**
- ❌ Re-upload content
- ❌ Commercial services
- ❌ Mass downloading without rate limiting

**yt-dlp is used as the core engine** (the industry standard for open-source media extraction).

---

## 🧠 How it Works: Smart Deduplication

Most YouTube subtitle downloaders just give you the raw VTT, which is full of repetition because YouTube "builds" sentences word-by-word in auto-generated captions. 

`ytknow` uses a **Prefix-Matching Algorithm**:
1. It strips all millisecond-level timestamps and inline tags.
2. It compares each new line with the previous one.
3. If the new line starts with the previous text, it "evolves" the line instead of repeating it.
4. If it's a duplicate or a subset, it's discarded.

**Result:** You get a clean, human-readable paragraph instead of a 10,000-line stuttering mess.

---

## 🧹 Before & After

`ytknow` cleans up the messy duplication and timing tags common in YouTube auto-captions:

### ❌ Before (Standard VTT)
```vtt
00:00:00.480 --> 00:00:03.070
das<00:00:00.640><c> heutige</c><00:00:01.079><c> Video</c>
00:00:03.070 --> 00:00:03.080
das heutige Video bedarf eines Vorworts
```

### ✅ After (ytknow Output)
> "Das heutige Video bedarf eines Vorworts..."

---

## ✨ Features

- 🚀 **Lightning Fast**: Uses `yt-dlp` with `--lazy-playlist` to start processing immediately, even on channels with 2000+ videos.
- 🧹 **Deep Cleaning**: Removes all VTT timing codes, word-level tags, and alignment metadata.
- 🧠 **Smart Deduplication**: Automatically resolves sentence-building repetition in YouTube's auto-captions.
- 🤖 **LLM-Optimized**: Generates clean TXT files with rich metadata headers and a consolidated JSONL master file.
- 📊 **Channel Survey**: Use `--survey` to scan available languages across a whole channel.
- 🌍 **Multi-Language Support**: Interactive menu to choose from original, manual, or auto-translated subtitles.
- 🔄 **Smart Fallback**: Automatically prefers `en-orig` if standard `en` is unavailable but requested.
- 🛡️ **Resilient**: Gracefully handles unavailable or private videos in large playlists.

---

## 🤖 RAG & LLM Readiness

`ytknow` is specifically designed for Retrieval-Augmented Generation (RAG). 

### Metadata Enrichment
Output files include header metadata (Source URL, Upload Date), allowing LLMs to cite sources and prioritize recent information.

### Master JSONL Export
Every session generates a `knowledge_master.jsonl` file. This format is the industry standard for:
*   **Model Fine-tuning**: directly usable as a training dataset.
*   **Archiving**: keeps full context per video.

### 🧩 Built-in Semantic Chunking
`ytknow` automatically generates a **second file** called `knowledge_chunks.jsonl`.
*   **Ready-to-Embed**: Splits text into ~1000 char chunks, respecting sentence boundaries.
*   **Overlapping**: Includes 100 char overlap to preserve context between chunks.
*   **Metadata Preserved**: Each chunk carries the video URL, title, and upload date.

> **Just upload `knowledge_chunks.jsonl` to your Vector DB (Pinecone, Chroma, Weaviate) and you're done!**

---

## 🛠️ Built With

* [![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)](https://www.python.org/)
* [![yt-dlp](https://img.shields.io/badge/yt--dlp-FF0000?style=for-the-badge&logo=youtube&logoColor=white)](https://github.com/yt-dlp/yt-dlp)
* [![FFmpeg](https://img.shields.io/badge/FFmpeg-007808?style=for-the-badge&logo=ffmpeg&logoColor=white)](https://ffmpeg.org/)

---

## 🛠️ Installation

```bash
# Clone the repository
git clone https://github.com/egohead/ytknow.git
cd ytknow

# Run the installer (macOS/Linux)
chmod +x install.sh
./install.sh
```

## 🚀 Usage

```bash
# Process a single video or channel
ytknow https://www.youtube.com/@ChannelName

# Survey a channel for available languages (first 50 videos)
ytknow --survey https://www.youtube.com/@ChannelName
```

## 📋 Requirements

- **Python 3.7+**
- **yt-dlp**: (Installed automatically via `install.sh`)
- **ffmpeg**: Required for some metadata extraction.

## 📁 Output Format

The app creates a directory for each session. Each video gets a `.txt` file with metadata headers, plus a master `JSONL` for RAG use.

```text
downloads/
└── ChannelName_en/
    ├── knowledge_master.jsonl    <-- Full context for each video
    ├── knowledge_chunks.jsonl    <-- 1000-char semantic chunks (RAG ready)
    ├── Video_Title_1.txt         <-- Human readable with metadata headers
    └── Video_Title_2.txt
```

## ❓ FAQ

**Q: Does it work with private videos?**
A: No, `ytknow` can only access public or unlisted content that you provide a URL for.

**Q: Is it safe against YouTube bans?**
A: We use `yt-dlp`'s optimized extraction methods. For massive channels, we recommend being patient as YouTube may temporarily throttle requests.

**Q: Can I use this for my RAG project?**
A: Yes! The JSONL output is designed specifically for tools like LangChain, LlamaIndex, or OpenAI Fine-tuning.

## 🤝 Contributing

Contributions are welcome! Feel free to open an issue or submit a pull request.

## ⚖️ MIT License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---
*This project respects content creators and YouTube's ToS.*
