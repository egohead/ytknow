import asyncio
import json
import logging
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import pandas as pd
import typer
import yaml
from tqdm.asyncio import tqdm
from typing_extensions import Annotated

# --- Configuration & Setup ---
APP_NAME = "yt-comments"
CONFIG_DIR = Path.home() / ".config" / APP_NAME
CONFIG_FILE = CONFIG_DIR / "config.yaml"

# Default Configuration
DEFAULT_CONFIG = {
    "output_dir": "comments_output",
    "format": "json",
    "max_comments": 1000,
    "min_likes": 0,
    "rate_limit": 2.0,
    "parallel": 4
}

# Logger
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(APP_NAME)

app = typer.Typer(help="YouTube Comments Downloader CLI", no_args_is_help=True)


# --- Helpers ---

def load_config():
    """Load configuration from yaml file or return defaults."""
    if not CONFIG_FILE.exists():
        return DEFAULT_CONFIG
    
    try:
        with open(CONFIG_FILE, "r") as f:
            user_config = yaml.safe_load(f) or {}
            # Merge with defaults
            config = DEFAULT_CONFIG.copy()
            config.update(user_config)
            return config
    except Exception as e:
        logger.warning(f"Failed to load config: {e}. Using defaults.")
        return DEFAULT_CONFIG

def save_default_config():
    """Create default config file if it doesn't exist."""
    if not CONFIG_FILE.exists():
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w") as f:
            yaml.dump(DEFAULT_CONFIG, f)
        logger.info(f"Created default config at {CONFIG_FILE}")

def get_yt_dlp_cmd(url: str, max_comments: int = 1000) -> List[str]:
    """Construct the yt-dlp command to extract comments."""
    # We use --dump-json to get metadata + comments
    # --write-comments is implicit if we ask for it in extraction, 
    # but strictly --get-comments might be deprecated or behave differently.
    # The most robust way to get ONLY comments metadata is often fetching the whole json.
    # However, for huge videos, this is heavy. 
    # yt-dlp has --get-comments option? No, it's usually automatic with --write-comments but that writes to file.
    # We want to pipe it.
    
    cmd = [
        "yt-dlp",
        "--dump-json",
        "--skip-download",
        "--no-playlist",
        "--write-comments", 
        # Limits
        # yt-dlp doesn't support strict "max comments" via CLI easily natively without extractor-args
        "--extractor-args", f"youtube:max_comments={max_comments},all,max_replies=50",
        url
    ]
    return cmd

async def extract_comments_async(url: str, config: dict) -> dict:
    """Run yt-dlp async to get comments."""
    cmd = get_yt_dlp_cmd(url, config.get("max_comments", 1000))
    
    # Rate limit check could go here
    await asyncio.sleep(config.get("rate_limit", 0.1))
    
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    
    stdout, stderr = await proc.communicate()
    
    if proc.returncode != 0:
        err_msg = stderr.decode().strip()
        logger.error(f"Failed to extract {url}: {err_msg}")
        return {}
        
    try:
        data = json.loads(stdout.decode())
        return data
    except json.JSONDecodeError:
        logger.error(f"Failed to parse JSON for {url}")
        return {}

def process_comment_data(raw_data: dict, min_likes: int = 0, keywords: List[str] = None) -> dict:
    """Clean and filter the raw json data."""
    if not raw_data:
        return None

    video_info = {
        "id": raw_data.get("id"),
        "title": raw_data.get("title"),
        "channel": raw_data.get("uploader"),
        "view_count": raw_data.get("view_count"),
        "upload_date": raw_data.get("upload_date")
    }
    
    raw_comments = raw_data.get("comments", [])
    cleaned_comments = []
    
    for c in raw_comments:
        like_count = c.get("like_count", 0)
        text = c.get("text", "")
        
        # Filters
        if like_count < min_likes:
            continue
            
        if keywords:
            # Check if ANY keyword is in text (case insensitive)
            if not any(k.lower() in text.lower() for k in keywords):
                continue

        cleaned_comments.append({
            "id": c.get("id"),
            "text": text,
            "author": {
                "name": c.get("author"),
                "id": c.get("author_id"),
                "is_uploader": c.get("author_is_uploader", False)
            },
            "likes": like_count,
            "timestamp": c.get("timestamp"), # Epoch
            "parent": "root"
        })
        
        # Handle replies? yt-dlp usually flattens or nests them depending on args?
        # Actually yt-dlp JSON output usually has them flat or in a specific way.
        # With current args they might be absent or present.
        # If we see replies logic? For now assume flat or top-level. 
        # The prompt asks for "Replies", so keeping them is good.
    
    return {
        "video": video_info,
        "comments": cleaned_comments
    }

def save_output(data: dict, output_dir: Path, fmt: str):
    """Save data to JSON, CSV, or Excel."""
    if not data or not data.get("comments"):
        return

    output_dir.mkdir(parents=True, exist_ok=True)
    video_id = data["video"]["id"]
    safe_title = "".join([c for c in data["video"]["title"] if c.isalnum() or c in (' ', '-', '_')]).strip()[:50]
    base_name = f"{safe_title}_{video_id}"
    
    # JSON
    if fmt == "json":
        out_path = output_dir / f"{base_name}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"Saved: {out_path}")

    # CSV / Excel
    elif fmt in ["csv", "excel"]:
        # Flatten for tabular
        rows = []
        for c in data["comments"]:
            row = {
                "video_id": video_id,
                "author": c["author"]["name"],
                "text": c["text"],
                "likes": c["likes"],
                "timestamp": c["timestamp"],
                "comment_id": c["id"]
            }
            rows.append(row)
            
        df = pd.DataFrame(rows)
        
        if fmt == "csv":
            out_path = output_dir / f"{base_name}.csv"
            df.to_csv(out_path, index=False)
            logger.info(f"Saved: {out_path}")
        else: # excel
            out_path = output_dir / f"{base_name}.xlsx"
            df.to_excel(out_path, index=False)
            logger.info(f"Saved: {out_path}")


# --- Commands ---

def download_video_comments(
    url: str, 
    output_dir: Path, 
    format: str = "json",
    max_comments: Optional[int] = None,
    min_likes: int = 0,
    filter_keywords: Optional[List[str]] = None
) -> bool:
    """Reusable function to download comments for a URL."""
    config = load_config()
    current_config = config.copy()
    current_config.update({
        "min_likes": min_likes,
        "rate_limit": 0
    })
    
    if max_comments is not None:
        current_config["max_comments"] = max_comments
    
    import asyncio
    try:
        data = asyncio.run(extract_comments_async(url, current_config))
        processed = process_comment_data(data, min_likes, filter_keywords)
        
        if processed:
            save_output(processed, output_dir, format)
            return True
    except Exception as e:
        logger.error(f"Error in download_video_comments: {e}")
    
    return False

@app.command()
def video(
    url: str, 
    format: Annotated[str, typer.Option(help="Output format: json, csv, excel")] = "json",
    output: Annotated[Path, typer.Option(help="Output directory")] = Path("./comments"),
    max_comments: int = 1000,
    min_likes: int = 0,
    filter_keywords: Optional[str] = None
):
    """Download comments for a single video."""
    keywords = [k.strip() for k in filter_keywords.split(",")] if filter_keywords else None
    
    success = download_video_comments(
        url, output, format, max_comments, min_likes, keywords
    )
    
    if success:
        print(f"✅ Comments processed.")
    else:
        print("❌ No comments found or extraction failed.")

@app.command()
def channel(
    url: str,
    max_videos: int = 50,
    format: str = "json",
    output: Path = Path("./comments"),
    parallel: int = 4
):
    """Download comments for all videos in a channel (up to max_videos)."""
    # 1. Get Video List
    print(f"🔍 Scanning channel for top {max_videos} videos...")
    cmd = [
        "yt-dlp", 
        "--flat-playlist", 
        "--print", "url", 
        "--playlist-end", str(max_videos),
        url
    ]
    res = os.popen(" ".join(cmd)).read()
    video_urls = [u.strip() for u in res.splitlines() if u.strip()]
    
    if not video_urls:
        print("❌ No videos found.")
        return

    print(f"found {len(video_urls)} videos. Starting batch...")
    # Delegate to batch logic
    batch(urls_file=None, parallel=parallel, format=format, output=output, _direct_urls=video_urls)


@app.command()
def batch(
    urls_file: Optional[Path] = typer.Argument(None, help="Text file with one URL per line"),
    parallel: int = 4,
    format: str = "json",
    output: Path = Path("./comments"),
    _direct_urls: Optional[List[str]] = None
):
    """Process a batch of URLs from a file."""
    urls = []
    if _direct_urls:
        urls = _direct_urls
    elif urls_file and urls_file.exists():
        with open(urls_file, "r") as f:
            urls = [line.strip() for line in f if line.strip()]
    else:
        print("❌ Please provide a URLs file.")
        return

    config = load_config()
    
    async def process_batch():
        sem = asyncio.Semaphore(parallel)
        
        async def worker(u):
            async with sem:
                data = await extract_comments_async(u, config)
                processed = process_comment_data(
                    data, 
                    config.get("min_likes", 0), 
                    None # Keyword filter not in batch CLI arg spec for simplicity, usually from config
                )
                if processed:
                    save_output(processed, output, format)
                    return 1
                return 0

        # Progress bar
        tasks = [worker(u) for u in urls]
        results = []
        for f in tqdm.as_completed(tasks, desc="Processing videos"):
            results.append(await f)
            
        print(f"Batch complete. Processed {sum(results)}/{len(urls)} videos successfully.")

    asyncio.run(process_batch())

@app.command()
def setup_config():
    """Create default config file."""
    save_default_config()


if __name__ == "__main__":
    app()
