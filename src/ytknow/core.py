import re
import sys
import json
import shutil
import logging
import subprocess
import textwrap
from pathlib import Path
from typing import Optional

from .config import LOG_FILE, Fore, Style
from .utils import check_dependencies, handle_ytdlp_error, print_progress
from .cleaning import clean_vtt_content, chunk_text
from .ai import transcribe_with_whisper, generate_summary_llm

try:
    from .comments import download_video_comments
except ImportError:
    download_video_comments = None

logger = logging.getLogger(__name__)

def get_source_title(url: str) -> str:
    """Gets the channel name (uploader) to use as the root directory."""
    try:
        # Always try to get the uploader/channel name first
        cmd = ["yt-dlp", "--print", "%(uploader)s", "--playlist-items", "1", url]
        
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        if result.stdout.strip():
            title = result.stdout.strip().splitlines()[0]
            # Clean it up strictly
            return re.sub(r'[^\w\-]', '_', title)
        
        # Fallback to title if uploader fails (rare)
        cmd_fallback = ["yt-dlp", "--get-title", "--no-playlist", url]
        res_fall = subprocess.run(cmd_fallback, capture_output=True, text=True)
        if res_fall.stdout.strip():
            return re.sub(r'[^\w\-]', '_', res_fall.stdout.strip())
            
        return "Unknown_Source"
    except Exception as e:
        handle_ytdlp_error(e, "get_source_title")
        return re.sub(r'[^\w\-]', '_', url.split('@')[-1] if '@' in url else "knowledge")

def run_channel_survey(url: str, limit: int = 50):
    """Scans a channel/playlist and reports subtitle availability statistics."""
    print(f"\n{Fore.CYAN}🔍 Surveying channel/playlist (scanning up to {limit} videos)...")
    
    cmd = [
        "yt-dlp",
        "--get-filename", # Minimally invasive
        "--print", "title",
        "--print", "subtitles",
        "--print", "automatic_captions",
        "--playlist-end", str(limit),
        "--ignore-errors",
        url
    ]
    
    # This is a bit complex to parse from one output stream, so strictly speaking
    # using --dump-json is cleaner but slower. Let's stick to --dump-json for reliability in survey.
    cmd = [
        "yt-dlp",
        "--dump-json",
        "--playlist-end", str(limit),
        "--flat-playlist", # Much faster, but only gives basic info. 
        # For subs we need deep info, which is slow.
        # Compromise: We skip flat playlist to get sub info, but limit count.
        "--ignore-errors",
        url
    ]
    
    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        
        counts = {"total": 0, "manual_subs": 0, "auto_subs": 0, "langs": {}}
        
        print(f"{Fore.WHITE}Fetching metadata... ", end="", flush=True)
        
        for line in process.stdout:
            try:
                data = json.loads(line)
                counts["total"] += 1
                
                has_manual = "subtitles" in data and data["subtitles"]
                has_auto = "automatic_captions" in data and data["automatic_captions"]
                
                if has_manual: counts["manual_subs"] += 1
                if has_auto: counts["auto_subs"] += 1
                
                # Aggregate languages
                langs = set()
                if has_manual:
                    langs.update(data["subtitles"].keys())
                if has_auto:
                    langs.update(data["automatic_captions"].keys())
                    
                for l in langs:
                    counts["langs"][l] = counts["langs"].get(l, 0) + 1
                    
                if counts["total"] % 5 == 0:
                    sys.stdout.write(".")
                    sys.stdout.flush()
            except Exception:
                pass
                
        print(" Done.\n")
        
        print(f"{Fore.GREEN}📊 Survey Results (First {counts['total']} videos):")
        print(f"  - Videos with manual subs: {counts['manual_subs']}")
        print(f"  - Videos with auto subs:   {counts['auto_subs']}")
        print(f"\n{Fore.CYAN}  Top Languages Available:")
        
        # Sort langs by frequency
        sorted_langs = sorted(counts["langs"].items(), key=lambda x: x[1], reverse=True)[:10]
        for l, count in sorted_langs:
            print(f"    - {l}: {count} videos")
            
    except Exception as e:
        print(f"\n{Fore.RED}✗ Survey failed: {e}")

def get_available_languages(url: str, is_channel: bool) -> list:
    """Fetches available subtitle languages for a video or channel."""
    print(f"{Fore.WHITE}Scanning available subtitles for this {'channel' if is_channel else 'video'}...")
    
    # For channels, we just check the first video to guess standard
    cmd = [
        "yt-dlp",
        "--list-subs",
        "--playlist-items", "1", 
        url
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    output = result.stdout
    
    langs = []
    # Parse yt-dlp output is tricky, simpler is to use --dump-json again for the first video
    cmd_json = [
        "yt-dlp",
        "--dump-json",
        "--playlist-items", "1",
        url
    ]
    res_json = subprocess.run(cmd_json, capture_output=True, text=True)
    try:
        data = json.loads(res_json.stdout.splitlines()[0])
        
        # 1. Manual Subs (Always available/valid)
        if "subtitles" in data and data["subtitles"]:
            for code, info in data["subtitles"].items():
                name = info[0].get("name", code)
                langs.append((code + "-orig", name, "[Original]"))
                
        # 2. Auto Subs (Filter for original language only)
        # We want to avoid listing 100+ auto-translated languages.
        # We only look for the one matching the video's detected language.
        video_lang = data.get("language")
        
        if "automatic_captions" in data and data["automatic_captions"]:
            for code, info in data["automatic_captions"].items():
                name = info[0].get("name", code)
                
                # Logic: Is this the "source" auto-caption?
                # Case A: Matches video metadata language (e.g. 'en' == 'en')
                is_original_auto = False
                if video_lang and code.startswith(video_lang):
                    is_original_auto = True
                
                # Case B: If no video language, usually 'en' or 'en-orig' or matches the first one?
                # Often the "original" is just the one that is NOT a translation. 
                # Hard to tell perfectly from JSON, but usually matching the manual sub language is a good hint.
                
                if is_original_auto:
                    tag = "[Auto-Generated]"
                    langs.append((code, name, tag))
                elif code == "en" and not video_lang: 
                    # Fallback: if unknown, English is often the base
                    langs.append((code, name, "[Auto-Generated?]"))

    except Exception:
        pass
        
    return langs

def process_url(url: str, output_dir: Path, lang_code: str = "en", enable_summarize: bool = False, whisper_model: str = "base", enable_comments: bool = False, skip_media: bool = False) -> Optional[tuple]:
    """Downloads and processes subtitles with a clean progress UI. Returns (final_file_path, video_count) or None."""
    check_dependencies()
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    source_slug = get_source_title(url)
    print(f"{Fore.CYAN}📥 Source:   {source_slug}")
    print(f"{Fore.CYAN}🌍 Language: {lang_code}")
    print("-" * 60)
    # Create Channel Root Directory
    channel_dir = output_dir / source_slug
    channel_dir.mkdir(parents=True, exist_ok=True)
    
    # Temp dir inside channel folder
    temp_dir = channel_dir / "tmp"
    temp_dir.mkdir(exist_ok=True)
    
    # Subdir for individual video folders
    videos_sub_dir = channel_dir / "videos"
    videos_sub_dir.mkdir(exist_ok=True)
    
    # yt-dlp command to get subtitles AND metadata
    if skip_media:
        # Metadata ONLY (for comments/survey)
        cmd = [
            "yt-dlp",
            "--skip-download",
            "--write-info-json",
            "--output", f"{temp_dir}/%(title)s.%(ext)s",
            "--newline",
            "--lazy-playlist",
            "--ignore-errors",
            url
        ]
        print(f"{Fore.WHITE}Step 1/3: Fetching Metadata (Media Download Skipped)...")
    else:
        # Standard Knowledge Base (Subs/Audio)
        sub_pattern = f"{lang_code}.*"
        cmd = [
            "yt-dlp",
            "--skip-download",
            "--write-subs",
            "--write-auto-subs",
            "--write-info-json", # Get rich metadata
            "--sub-langs", sub_pattern,
            "--output", f"{temp_dir}/%(title)s.%(ext)s",
            "--newline",
            "--lazy-playlist",
            "--progress-template", "DOWNLOAD_PROGRESS:%(progress._percent_str)s",
            "--ignore-errors",
            url
        ]
        print(f"{Fore.WHITE}Step 1/3: Downloading Subtitles & Metadata...")
    print(f"{Fore.BLACK}{Style.BRIGHT}Scanning channel for videos (this might take a moment)...")
    
    current_video_title = "Video"
    last_status = ""
    try:
        with open(LOG_FILE, "a") as log:
            log.write(f"\n--- Starting Download: {url} ---\n")
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
            
            for line in process.stdout:
                log.write(line)
                clean_line = line.strip()
                
                if "[info] Writing video subtitles to:" in clean_line or "[info] Writing video metadata as JSON to:" in clean_line:
                    try:
                        path_part = clean_line.split("to:", 1)[-1].strip()
                        file_name = Path(path_part).name
                        title_part = re.sub(r'\.[a-z]{2}(-[a-zA-Z0-9]+)?\.vtt$', '', file_name)
                        title_part = re.sub(r'\.info\.json$', '', title_part)
                        if title_part:
                            current_video_title = title_part
                    except Exception:
                        pass

                if clean_line.startswith("[") and "DOWNLOAD_PROGRESS" not in clean_line:
                    tag = clean_line.split("]", 1)[0] + "]" if "]" in clean_line else ""
                    if tag in ["[youtube]", "[info]", "[download]"] and clean_line != last_status:
                        sys.stdout.write("\r\033[K")
                        display_line = (clean_line[:70] + '..') if len(clean_line) > 70 else clean_line
                        print(f"{Fore.BLACK}{Style.BRIGHT}{display_line}")
                        last_status = clean_line

                if "DOWNLOAD_PROGRESS:" in clean_line:
                    try:
                        p_str = clean_line.split("DOWNLOAD_PROGRESS:")[-1].strip().split(" ")[0].replace('%', '')
                        p_float = float(p_str)
                        short_title = (current_video_title[:20] + '..') if len(current_video_title) > 20 else current_video_title
                        print_progress(p_float, 100, prefix=f'Fetching {short_title}', suffix='')
                    except (ValueError, IndexError):
                        pass
            
            process.wait()
                
    except Exception as e:
         handle_ytdlp_error(e, "process_url")
         if 'temp_dir' not in locals():
             return None

    vtt_files = list(temp_dir.glob("*.vtt"))
    
    # --- Whisper Fallback Logic ---
    is_audio_fallback = False
    
    # If we are NOT skipping media, we check for subs/audio
    if not skip_media:
        if not vtt_files:
            print(f"\n{Fore.YELLOW}⚠ No subtitles found for language '{lang_code}'.")
            print(f"{Fore.YELLOW}⚠ Attempting audio download and Whisper transcription...")
            
            # 1. Download Audio
            audio_cmd = [
                "yt-dlp",
                # We need to download audio now since subs failed
                "--extract-audio", 
                "--audio-format", "m4a",
                "--write-info-json",
                "--output", f"{temp_dir}/%(title)s.%(ext)s",
                "--newline",
                "--ignore-errors",
                url            
            ]
            try:
                 subprocess.run(audio_cmd, check=True)
                 is_audio_fallback = True
            except Exception as e:
                 print(f"{Fore.RED}✗ Audio download failed: {e}")
                 # In knowledge extraction, this is fatal if we demand transcripts.
                 # But if we have comments enabled? maybe proceed?
                 # For now, return None as before unless we refactor deeper.
                 return None
    
            # 2. Check if audio files exist
            audio_files = list(temp_dir.glob("*.m4a"))
            if not audio_files:
                 print(f"{Fore.RED}✗ No audio files downloaded.")
                 return None
                 
    # --- End Whisper Logic setup --

    # Determine what files to process (VTTs, Audio Fallback, or Just Info JSONs if skipping media)
    if skip_media:
        # Use info.json files as the "source" to iterate over
        files_to_process = list(temp_dir.glob("*.info.json"))
    elif is_audio_fallback:
        files_to_process = list(temp_dir.glob("*.m4a"))
    else:
        files_to_process = vtt_files
        
    if not files_to_process:
        print(f"{Fore.RED}❌ No content found to process.")
        shutil.rmtree(temp_dir)
        return None

    jsonl_master = channel_dir / f"{source_slug}_master.jsonl"
    jsonl_chunks = channel_dir / f"{source_slug}_chunks.jsonl"
    master_txt_path = channel_dir / f"{source_slug}_master.txt"
    master_md_path = channel_dir / f"{source_slug}_master.md"
    
    total_files = len(files_to_process)
    print(f"{Fore.WHITE}Step 2/3: Processing {total_files} videos into '{channel_dir.name}/'...")
    
    import json
    processed_count = 0
    with open(jsonl_master, "w", encoding="utf-8") as j_master, \
         open(jsonl_chunks, "w", encoding="utf-8") as j_chunks, \
         open(master_txt_path, "w", encoding="utf-8") as m_txt, \
         open(master_md_path, "w", encoding="utf-8") as m_md:
         
        for i, file_path in enumerate(files_to_process, 1):
            # Base name for metadata matching
            # VTT: .lang.vtt -> base  | Audio: .m4a -> base
            base_name = file_path.stem
            # Clean up suffix like .en or .de if it exists (for vtt)
            base_name = re.sub(r'\.[a-z]{2}(-[a-zA-Z0-9]+)?$', '', base_name)
            
            if skip_media:
                # If skipping media, we are iterating .info.json files directly
                # base_name is filename without suffix
                info_json_path = file_path
                clean_text = "" 
            else:
                info_json_path = list(temp_dir.glob(f"{re.escape(base_name)}*.info.json"))
                info_json_path = info_json_path[0] if info_json_path else None
            
            # Extract metadata if available
            metadata = {}
            if info_json_path and info_json_path.exists():
                try:
                    with open(info_json_path, "r", encoding="utf-8") as j:
                        raw_meta = json.load(j)
                        metadata = {
                            "title": raw_meta.get("title", ""),
                            "url": raw_meta.get("webpage_url", ""),
                            "date": raw_meta.get("upload_date", ""),
                            "description": raw_meta.get("description", ""),
                            "channel": raw_meta.get("uploader", ""),
                            "view_count": raw_meta.get("view_count", 0)
                        }
                except Exception:
                    pass

            print_progress(i, total_files, prefix='Optimizing ', suffix=f'({i}/{total_files})')
            
            try:
                clean_text = ""
                
                if not skip_media:
                    if is_audio_fallback:
                        # TRANSCRIBE
                        clean_text = transcribe_with_whisper(file_path, model_name=whisper_model)
                    else:
                        # READ VTT
                        with open(file_path, "r", encoding="utf-8") as f:
                            content = f.read()
                        clean_text = clean_vtt_content(content)
                
                # Base processing for folder structure
                # Even if clean_text is empty, we validly want the folder for comments
                video_title = metadata.get("title") or base_name
                safe_title = re.sub(r'[^\w\-]', '_', video_title)[:100]
                
                # Create Video Subdirectory inside 'videos' folder
                video_dir = videos_sub_dir / safe_title
                video_dir.mkdir(exist_ok=True)
                
                if clean_text:
                    
                    target_file = video_dir / f"{safe_title}.txt"
                    
                    
                    # 1. Save TXT with Full Metadata Context (Individual)
                    txt_header = ""
                    txt_header += f"TITLE: {video_title}\n"
                    if metadata.get("url"): txt_header += f"URL:   {metadata['url']}\n"
                    if metadata.get("date"): txt_header += f"DATE:  {metadata['date']}\n"
                    if metadata.get("description"):
                        txt_header += f"DESCRIPTION:\n{textwrap.indent(metadata['description'][:500] + '...', '  ')}\n"
                    txt_header += "-" * 60 + "\n\n"
                    
                    full_txt_content = txt_header + clean_text + "\n"
                    
                    with open(target_file, "w", encoding="utf-8") as f:
                        f.write(full_txt_content)
                        
                    # Append to MASTER TXT
                    m_txt.write(full_txt_content + "\n" + "="*60 + "\n\n")
                    
                    # 1b. Save MD (Markdown) (Individual)
                    md_header = ""
                    md_header += f"# {video_title}\n\n"
                    if metadata.get("url"): md_header += f"**URL:** [{metadata['url']}]({metadata['url']})\n"
                    if metadata.get("channel"): md_header += f"**Channel:** {metadata['channel']}\n"
                    if metadata.get("date"): md_header += f"**Date:** {metadata['date']}\n"
                    if metadata.get("description"):
                        md_header += f"\n> **Description:**\n> {metadata['description'][:500].replace(chr(10), chr(10)+'> ') + '...'}\n"
                    md_header += "\n---\n\n"
                    
                    full_md_content = md_header + clean_text + "\n"
                    
                    target_md = video_dir / f"{safe_title}.md"
                    with open(target_md, "w", encoding="utf-8") as f:
                        f.write(full_md_content)
                    
                    # Append to MASTER MD
                    m_md.write(full_md_content + "\n---\n\n")
                    
                    # 2. Append to MASTER JSONL (Full Text)
                    json_entry = {
                        "content": clean_text,
                        "metadata": metadata
                    }
                    j_master.write(json.dumps(json_entry, ensure_ascii=False) + "\n")
                    
                    # 3. Generate & Append CHUNKS to CHUNKS JSONL
                    chunk_meta = {k: v for k, v in metadata.items() if k in ['title', 'url', 'date', 'channel']}
                    
                    chunks = chunk_text(clean_text, chunk_size=1000, overlap=100)
                    for idx, chunk in enumerate(chunks):
                        chunk_entry = {
                            "chunk_id": f"{safe_title}_{idx}",
                            "content": chunk,
                            "metadata": chunk_meta
                        }
                        j_chunks.write(json.dumps(chunk_entry, ensure_ascii=False) + "\n")
                    
                    # 4. Generate SUMMARY (if requested)
                    if enable_summarize:
                         summary = generate_summary_llm(clean_text, metadata)
                         if summary:
                             summary_file = video_dir / f"{safe_title}_summary.md"
                             with open(summary_file, "w", encoding="utf-8") as f:
                                 f.write(summary)
                    
                # 5. Download Comments (if enabled)
                # Check regardless of clean_text availability
                if enable_comments and download_video_comments:
                     vid_url = metadata.get("url") or metadata.get("webpage_url")
                     if vid_url:
                         print(f"   {Fore.CYAN}💬 Downloading comments...", end="\r")
                         # Use 'json' format for raw data, save in video_dir
                         download_video_comments(vid_url, video_dir, format="json")
                         print(f"   {Fore.GREEN}💬 Comments saved.      ")
                
                processed_count += 1
            except Exception as e:
                logger.error(f"Failed to process {file_path.name}: {e}")
            
    # Cleanup temp folder
    # User requested to keep tmp files: "temp for individual download files"
    # shutil.rmtree(temp_dir)
    return (channel_dir, processed_count)
