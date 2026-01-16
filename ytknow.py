#!/usr/bin/env python3
"""
YouTube to Knowledge CLI App
Extracts clean text from YouTube channel subtitles for RAG/LLM use.
"""

import os
import re
import sys
import shutil
import logging
import argparse
import subprocess
from pathlib import Path
from html import unescape
from typing import List, Optional, Dict
import textwrap

try:
    from colorama import init, Fore, Style
    init(autoreset=True)
except ImportError:
    # Fallback if colorama is not installed yet
    class FakeColor:
        def __getattr__(self, name):
            return ""
    Fore = Style = FakeColor()

# Configuration
LOG_FILE = "conversion.log"
DEFAULT_OUTPUT_DIR = "downloads"

# Native language mapping (Top languages)
NATIVE_LANG_NAMES = {
    'af': 'Afrikaans', 'am': 'አማርኛ', 'ar': 'العربية', 'as': 'অসমীয়া', 'az': 'Azərbaycanca',
    'be': 'Беларуская', 'bg': 'Български', 'bn': 'বাংলা', 'bs': 'Bosanski', 'ca': 'Català',
    'cs': 'Čeština', 'cy': 'Cymraeg', 'da': 'Dansk', 'de': 'Deutsch', 'el': 'Ελληνικά',
    'en': 'English', 'eo': 'Esperanto', 'es': 'Español', 'et': 'Eesti', 'eu': 'Euskara',
    'fa': 'فارسی', 'fi': 'Suomi', 'fil': 'Filipino', 'fr': 'Français', 'ga': 'Gaeilge',
    'gl': 'Galego', 'gu': 'ગુજરાતી', 'ha': 'Hausa', 'he': 'עברית', 'hi': 'हिन्दी',
    'hr': 'Hrvatski', 'hu': 'Magyar', 'hy': 'Հայերեն', 'id': 'Bahasa Indonesia', 'ig': 'Igbo',
    'is': 'Íslenska', 'it': 'Italiano', 'ja': '日本語', 'jv': 'Basa Jawa', 'ka': 'ქართული',
    'kk': 'Қазақ тілі', 'km': 'ខ្មែរ', 'kn': 'ಕನ್ನಡ', 'ko': '한국어', 'ku': 'Kurdî',
    'ky': 'Кыргызча', 'la': 'Latina', 'lb': 'Lëtzebuergesch', 'lo': 'ລາວ', 'lt': 'Lietuvių',
    'lv': 'Latviešu', 'mg': 'Malagasy', 'mi': 'Māori', 'mk': 'Македонски', 'ml': 'മലയാളം',
    'mn': 'Монгол', 'mr': 'मराठी', 'ms': 'Bahasa Melayu', 'mt': 'Malti', 'my': 'မြန်မာ',
    'ne': 'नेपाली', 'nl': 'Nederlands', 'no': 'Norsk', 'ny': 'Chichewa', 'or': 'ଓଡ଼િଆ',
    'pa': 'ਪੰਜਾਬੀ', 'pl': 'Polski', 'ps': 'پښتو', 'pt': 'Português', 'qu': 'Quechua',
    'ro': 'Română', 'ru': 'Русский', 'rw': 'Kinyarwanda', 'sd': 'سنڌي', 'si': 'සිංහල',
    'sk': 'Slovenčina', 'sl': 'Slovenščina', 'sm': 'Gagana Samoa', 'sn': 'chiShona',
    'so': 'Soomaali', 'sq': 'Shqip', 'sr': 'Српски', 'st': 'Sesotho', 'su': 'Basa Sunda',
    'sv': 'Svenska', 'sw': 'Kiswahili', 'ta': 'தமிழ்', 'te': 'తెలుగు', 'tg': 'Тоҷикӣ',
    'th': 'ไทย', 'tk': 'Türkmençe', 'tr': 'Türkçe', 'tt': 'Татарча', 'ug': 'ئۇيغۇرچە',
    'uk': 'Українська', 'ur': 'اردو', 'uz': 'Oʻzbekcha', 'vi': 'Tiếng Việt', 'xh': 'isiXhosa',
    'yi': 'ייִדיש', 'yo': 'Yorùbá', 'zh-Hans': '简体中文', 'zh-Hant': '繁體中文', 'zu': 'isiZulu'
}

def get_native_name(lang_code: str) -> str:
    """Returns the native name for a language code if available."""
    # Strip suffixes like -orig, -en, etc. for mapping
    base_code = lang_code.split('-')[0]
    return NATIVE_LANG_NAMES.get(lang_code, NATIVE_LANG_NAMES.get(base_code, ""))

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# ASCII Art Banner
BANNER = f"""{Fore.CYAN}
 __   __  _______  ___   _  __    _  _______  _     _ 
|  | |  ||       ||   | | ||  |  | ||       || | _ | |
|  |_|  ||_     _||   |_| ||   |_| ||   _   || || || |
|       |  |   |  |      _||       ||  | |  ||       |
|_     _|  |   |  |     |_ |  _    ||  |_|  ||   _   |
  |   |    |   |  |    _  || | |   ||       ||  | |  |
  |___|    |___|  |___| |_||_|  |__||_______||__| |__|
{Fore.MAGENTA}  >>> YouTube to Knowledge CLI App <<<
"""

def print_banner():
    """Prints the application banner."""
    print(BANNER)
    print(f"{Fore.WHITE}Extract clean knowledge from YouTube for RAG, Notion & LLMs")
    print("=" * 60)

def check_dependencies():
    """Check if yt-dlp and ffmpeg are installed."""
    deps = ["yt-dlp", "ffmpeg"]
    missing = []
    for dep in deps:
        if not shutil.which(dep):
            missing.append(dep)
    
    if missing:
        print(f"{Fore.RED}✗ Error: Missing system dependencies.")
        print(f"{Fore.YELLOW}Required: {', '.join(missing)}")
        print(f"{Fore.WHITE}Install via Homebrew: {Fore.GREEN}brew install {' '.join(missing)}")
        sys.exit(1)
    
    print(f"{Fore.GREEN}✓ Dependencies: yt-dlp found, ffmpeg found")

import textwrap

def clean_vtt_content(vtt_text: str) -> str:
    """Removes timestamps, tags, and handles repetition in YouTube auto-subs."""
    # 1. Global tag removal (e.g. <c>, word-level timestamps <00:00:00.000>)
    vtt_text = re.sub(r'<[^>]+>', '', vtt_text)
    
    # 2. Extract meaningful lines
    lines = vtt_text.splitlines()
    clean_lines = []
    for line in lines:
        line = line.strip()
        # Skip VTT meta/header
        if not line or any(x in line for x in ["WEBVTT", "Kind:", "Language:", "-->"]):
            continue
        # Skip digit-only lines
        if line.isdigit():
            continue
            
        # Decode HTML entities
        line = unescape(line).strip()
        if line:
            clean_lines.append(line)
    
    # 3. Robust Deduplication for YouTube Auto-Subs
    # Problem: YouTube sends blocks like ["A"], ["A", "B"], ["B", "C"], ["C", "D"]
    # We use a prefix-checking strategy to only keep the unique/building content.
    final_text_chunks = []
    for line in clean_lines:
        if not final_text_chunks:
            final_text_chunks.append(line)
            continue
        
        last_line = final_text_chunks[-1]
        
        # If current line starts with the last line, it's a "building" line
        if line.startswith(last_line):
            final_text_chunks[-1] = line
        # If last line already contains the current line as a prefix, skip
        elif last_line.startswith(line):
            continue
        else:
            final_text_chunks.append(line)
            
    # Join into a single block of text
    full_text = " ".join(final_text_chunks)
    # Cleanup multiple spaces
    full_text = re.sub(r'\s+', ' ', full_text).strip()
    
    # Format for readability
    if not full_text:
        return ""
    return textwrap.fill(full_text, width=100)

def handle_ytdlp_error(e: Exception, context: str):
    """Handles yt-dlp specific errors, particularly rate limits."""
    error_msg = str(e)
    
    # Also check the log file for 429 error if it's not in the exception message
    log_context = ""
    try:
        if Path(LOG_FILE).exists():
            with open(LOG_FILE, "r") as f:
                # Read last 10 lines
                log_entries = f.readlines()[-10:]
                log_context = "".join(log_entries)
    except Exception:
        pass

    full_error_context = error_msg + log_context
    logger.error(f"{context} failed: {error_msg}")
    
    if "429" in full_error_context or "Too Many Requests" in full_error_context:
        print(f"\n{Fore.RED}{'!' * 60}")
        print(f"{Fore.RED}⚠ YOUTUBE RATE LIMIT DETECTED (HTTP 429)")
        print(f"{Fore.YELLOW}YouTube is temporarily blocking your connection because of too many")
        print(f"{Fore.YELLOW}requests. This is common when scanning many videos or languages.")
        print(f"{Fore.WHITE}Wait ~15 minutes and try again.")
        print(f"{Fore.RED}{'!' * 60}\n")
    else:
        # Show a generic error if it wasn't a 429
        print(f"\n{Fore.RED}✗ Error: {context} failed. Check {LOG_FILE} for details.")

def get_source_title(url: str) -> str:
    """Gets the uploader or playlist/video title for naming the output file."""
    try:
        # Try to get uploader (for channels) or title (for single videos)
        cmd = ["yt-dlp", "--get-title", "--no-playlist", url]
        if "@" in url or "/channel/" in url or "/user/" in url or "/c/" in url:
            # For channels, uploader might be better, but --get-title on a channel usually gives nothing or first video
            # So we use a different approach for channels if needed.
            # Actually, yt-dlp --print "%(uploader)s" is very reliable for channels.
            cmd = ["yt-dlp", "--print", "%(uploader)s", "--playlist-items", "1", url]
        
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        title = result.stdout.strip().splitlines()[0]
        return re.sub(r'[^\w\-]', '_', title)
    except Exception as e:
        handle_ytdlp_error(e, "get_source_title")
        # Fallback to URL-based slug if metadata fetching fails
        return re.sub(r'[^\w\-]', '_', url.split('@')[-1] if '@' in url else "knowledge")

def process_url(url: str, output_dir: Path):
    """Downloads and processes subtitles from a YouTube URL (Channel or Video)."""
    check_dependencies()
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    source_slug = get_source_title(url)
    print(f"{Fore.CYAN}📥 Source identified: {source_slug}")
    print(f"{Fore.CYAN}📥 Downloading subtitles from: {url}")
    
    # We use a subfolder for raw VTTs
    temp_dir = output_dir / f"temp_{source_slug}"
    temp_dir.mkdir(exist_ok=True)
    
def run_channel_survey(url: str, limit: int = 50):
    """Scans a channel/playlist and reports subtitle availability statistics."""
    print(f"\n{Fore.CYAN}🔍 Surveying channel/playlist (scanning up to {limit} videos)...")
    print(f"{Fore.BLACK}{Style.BRIGHT}This might take a moment depending on the number of videos.")
    
    # We use -J for the first 'limit' items to get all metadata at once if possible
    # or use --print which is often faster.
    cmd = [
        "yt-dlp",
        "--flat-playlist",
        "--playlist-end", str(limit),
        "--print", "%(subtitles:keys)j, %(automatic_captions:keys)j",
        url
    ]
    
    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        stdout, stderr = process.communicate()
        
        if process.returncode != 0:
            handle_ytdlp_error(Exception(stderr), "run_channel_survey")
            return

        lines = stdout.strip().splitlines()
        total_videos = len(lines)
        
        if total_videos == 0:
            print(f"{Fore.YELLOW}⚠ No videos found in this survey range.")
            return

        import json
        from collections import Counter
        
        manual_counts = Counter()
        auto_counts = Counter()
        
        for line in lines:
            try:
                # Line format: ["en", "de"], ["en", "fr"]
                parts = line.split(", ", 1)
                if len(parts) == 2:
                    m_subs = json.loads(parts[0])
                    a_subs = json.loads(parts[1])
                    if m_subs: manual_counts.update(m_subs)
                    if a_subs: auto_counts.update(a_subs)
            except Exception:
                continue

        print(f"\n{Fore.GREEN}✅ Survey Complete for {total_videos} videos:")
        
        # Combine all unique codes
        all_codes = sorted(list(set(manual_counts.keys()) | set(auto_counts.keys())))
        
        # Priority sort: Original-like, English, then others
        def sort_key(code):
            if code.endswith("-orig"): return (0, code)
            if code == "en": return (1, code)
            return (2, code)
        
        all_codes.sort(key=sort_key)
        
        print(f"{'Code':<10} | {'Native Name':<20} | {'Manual':<8} | {'Auto-Trans.':<10}")
        print("-" * 65)
        
        for code in all_codes[:25]: # Show top 25
            native = get_native_name(code)
            m_count = manual_counts.get(code, 0)
            a_count = auto_counts.get(code, 0)
            
            # Formatting
            m_str = f"{Fore.GREEN}{m_count}" if m_count > 0 else f"{Fore.WHITE}0"
            a_str = f"{Style.BRIGHT}{a_count}" if a_count > 0 else f"{Fore.WHITE}0"
            
            print(f"{code:<10} | {native:<20} | {m_str:<17} | {a_str}")
            
        if len(all_codes) > 25:
            print(f"{Fore.BLACK}{Style.BRIGHT}... and {len(all_codes) - 25} more languages.")
            
        print(f"\n{Fore.CYAN}Tip: Use 'ytknow [URL] -l [CODE]' to download the desired language.")

    except Exception as e:
        handle_ytdlp_error(e, "run_channel_survey")

def get_available_languages(url: str) -> Dict[str, str]:
    """Scans for available subtitle languages and returns a mapping of {code: type}."""
    try:
        # Get subtitle info in JSON format
        cmd = ["yt-dlp", "--skip-download", "--print-json", "--no-playlist", "--playlist-items", "1", url]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        import json
        data = json.loads(result.stdout)
        
        subs = data.get("subtitles", {})
        auto_subs = data.get("automatic_captions", {})
        
        results = {}
        # Manual subtitles are [Manual]
        for code in subs.keys():
            results[code] = "[Manual]"
        
        # Auto captions: the ones that aren't also manual are [Auto]
        for code in auto_subs.keys():
            if code not in results:
                # If it's a code like 'de' and the video is German, it's Source.
                # If it's 100+ others, they are usually Auto-Translated.
                # A good heuristic: if it's in the list of 100+ languages but not manual, it's auto-generated/translated.
                results[code] = "[Auto]"
                
        return results
    except Exception as e:
        handle_ytdlp_error(e, "get_available_languages")
        return {}

def get_key():
    """Reads a single keypress from the terminal."""
    import tty, termios
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(sys.stdin.fileno())
        ch = sys.stdin.read(1)
        if ch == '\x1b': # Escape sequence
            ch += sys.stdin.read(2)
        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

def select_language_interactive(url: str, is_channel: bool) -> str:
    """Prompts user to select a language code using arrow keys."""
    if is_channel:
        print(f"{Fore.YELLOW}Channel detected. Enter preferred language code (e.g., 'en', 'de', 'fr'):")
        lang = input(f"{Fore.CYAN}Language code [default: en]: ").strip().lower()
        return lang if lang else "en"
    
    print(f"{Fore.CYAN}Scanning available subtitles for this video...")
    lang_map = get_available_languages(url)
    langs = sorted(list(lang_map.keys()))
    
    if not langs:
        print(f"{Fore.YELLOW}No subtitles found. Falling back to default 'en'.")
        return "en"
    
    # Priority sorting
    all_options = sorted(langs, key=lambda x: (
        0 if x.endswith("-orig") else 
        1 if x == "en" else 
        2 if lang_map.get(x) == "[Manual]" else 3
    ))
    selected_idx = 0
    
    print(f"{Fore.GREEN}Use UP/DOWN arrows to select, ENTER to confirm:")
    print(f"{Fore.BLACK}{Style.BRIGHT}(Many options are on-the-fly 'Auto-Translations' by YouTube)")
    
    # Simple interactive loop
    while True:
        # Hide cursor and move up to redraw
        sys.stdout.write("\033[?25l") 
        
        # Display options (scrollable-like if too many)
        window_size = 15
        start_idx = max(0, selected_idx - window_size // 2)
        end_idx = min(len(all_options), start_idx + window_size)
        
        # Clear lines for redraw (using ANSI escape codes)
        for i in range(window_size + 2): # extra line for the tip
            sys.stdout.write("\033[K\n")
        sys.stdout.write(f"\033[{window_size + 2}A")

        for i in range(start_idx, end_idx):
            lang = all_options[i]
            prefix = f"{Fore.CYAN}➔ " if i == selected_idx else "  "
            style = Fore.WHITE + Style.BRIGHT if i == selected_idx else Fore.WHITE
            
            # Get native name
            native_name = get_native_name(lang)
            display_name = f"{lang.ljust(10)} ({native_name})" if native_name else lang
            
            # Map type labels
            m_type = lang_map.get(lang, "")
            type_label = ""
            if lang.endswith("-orig"):
                type_label = f"{Fore.YELLOW}[Original]"
            elif m_type == "[Manual]":
                type_label = f"{Fore.GREEN}[Manual]"
            elif m_type == "[Auto]":
                # For common ones like 'en', keep it English, otherwise Auto-Translate
                if lang == "en":
                    type_label = f"{Fore.BLUE}[Auto-English]"
                else:
                    type_label = f"{Fore.BLACK}{Style.BRIGHT}[Auto-Translate]"
            
            print(f"{prefix}{style}{display_name.ljust(30)} {type_label}")
            
        if end_idx < len(all_options):
            print(f"  {Fore.BLACK}{Style.BRIGHT}... and {len(all_options) - end_idx} more")
        else:
            print("")

        key = get_key()
        
        if key == '\x1b[A': # UP
            selected_idx = (selected_idx - 1) % len(all_options)
        elif key == '\x1b[B': # DOWN
            selected_idx = (selected_idx + 1) % len(all_options)
        elif key in ['\r', '\n']: # ENTER
            break
        elif key == '\x03': # Ctrl+C
            sys.stdout.write("\033[?25h") # Show cursor
            sys.exit(0)
            
        # Move cursor back up for next frame
        sys.stdout.write(f"\033[{window_size + 2}A")

    sys.stdout.write("\033[?25h") # Show cursor
    print(f"\n{Fore.GREEN}✓ Selected: {all_options[selected_idx]}")
    return all_options[selected_idx]

def print_progress(current, total, prefix='', suffix='', length=40):
    """Prints a custom progress bar."""
    percent = ("{0:.1f}").format(100 * (current / float(total)))
    filled_length = int(length * current // total)
    bar = '█' * filled_length + '-' * (length - filled_length)
    # \033[K clears from cursor to end of line
    sys.stdout.write(f'\r{prefix} |{bar}| {percent}% {suffix}\033[K')
    sys.stdout.flush()
    if current == total:
        print()

def process_url(url: str, output_dir: Path, lang_code: str) -> Optional[tuple]:
    """Downloads and processes subtitles with a clean progress UI. Returns (final_file_path, video_count) or None."""
    check_dependencies()
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    source_slug = get_source_title(url)
    print(f"{Fore.CYAN}📥 Source:   {source_slug}")
    print(f"{Fore.CYAN}🌍 Language: {lang_code}")
    print("-" * 60)
    
    # We use a subfolder for raw VTTs
    temp_dir = output_dir / f"temp_{source_slug}_{lang_code}"
    temp_dir.mkdir(exist_ok=True)
    
    # yt-dlp command to get subtitles
    sub_pattern = f"{lang_code}.*"
    cmd = [
        "yt-dlp",
        "--skip-download",
        "--write-subs",
        "--write-auto-subs",
        "--sub-langs", sub_pattern,
        "--output", f"{temp_dir}/%(title)s.%(ext)s",
        "--newline",
        "--lazy-playlist", # Immediate processing
        "--progress-template", "DOWNLOAD_PROGRESS:%(progress._percent_str)s",
        "--ignore-errors", # Don't stop the whole process if one video fails
        url
    ]
    
    print(f"{Fore.WHITE}Step 1/2: Downloading Subtitles...")
    print(f"{Fore.BLACK}{Style.BRIGHT}Searching for videos with subtitles (this may take a moment)...")
    
    current_video_title = "Video"
    last_status = ""
    try:
        # Open log file for appending
        with open(LOG_FILE, "a") as log:
            log.write(f"\n--- Starting Download: {url} ---\n")
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
            
            for line in process.stdout:
                log.write(line)
                clean_line = line.strip()
                
                # Update title from [info] line
                if "[info] Writing video subtitles to:" in clean_line:
                    try:
                        path_part = clean_line.split("to:", 1)[-1].strip()
                        file_name = Path(path_part).name
                        title_part = re.sub(r'\.[a-z]{2}(-[a-zA-Z0-9]+)?\.vtt$', '', file_name)
                        if title_part:
                            current_video_title = title_part
                    except Exception:
                        pass

                # Show extraction status lines to keep user informed, but avoid duplicates/spam
                if clean_line.startswith("[") and "DOWNLOAD_PROGRESS" not in clean_line:
                    tag = clean_line.split("]", 1)[0] + "]" if "]" in clean_line else ""
                    if tag in ["[youtube]", "[info]", "[download]"] and clean_line != last_status:
                        # Clear progress bar before printing status
                        sys.stdout.write("\r\033[K")
                        # Truncate strictly to avoid wrapping
                        display_line = (clean_line[:70] + '..') if len(clean_line) > 70 else clean_line
                        print(f"{Fore.BLACK}{Style.BRIGHT}{display_line}")
                        last_status = clean_line

                if "DOWNLOAD_PROGRESS:" in clean_line:
                    try:
                        p_str = clean_line.split("DOWNLOAD_PROGRESS:")[-1].strip().split(" ")[0].replace('%', '')
                        p_float = float(p_str)
                        # Short prefix to avoid wrapping
                        short_title = (current_video_title[:20] + '..') if len(current_video_title) > 20 else current_video_title
                        print_progress(p_float, 100, prefix=f'Downloading {short_title}', suffix='')
                    except (ValueError, IndexError):
                        pass
            
            process.wait()
            # We ignore process.returncode here because we check vtt_files below.
            # Large channels often have some failed items even if others succeed.
                
    except Exception as e:
        # Only treat as fatal if we have NO files
        vtt_files = list(temp_dir.glob("*.vtt"))
        if not vtt_files:
            handle_ytdlp_error(e, "process_url")
            return None

    vtt_files = list(temp_dir.glob("*.vtt"))
    if not vtt_files:
        print(f"\n{Fore.YELLOW}⚠ No subtitles found for language '{lang_code}' at this URL.")
        return None

    # Prepare the single output file
    final_file = output_dir / f"{source_slug}_{lang_code}_complete.txt"
    total_files = len(vtt_files)
    
    print(f"{Fore.WHITE}Step 2/2: Processing & Merging {total_files} files...")
    
    with open(final_file, "w", encoding="utf-8") as out:
        for i, vtt_path in enumerate(vtt_files, 1):
            # Extract video title from filename
            video_title = re.sub(r'\.[a-z]{2}(-[a-zA-Z0-9]+)?\.vtt$', '', vtt_path.name)
            
            # Print progress for processing
            print_progress(i, total_files, prefix='Processing ', suffix=f'({i}/{total_files})')
            
            with open(vtt_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            clean_text = clean_vtt_content(content)
            
            out.write("=" * 80 + "\n")
            out.write(f"VIDEO: {video_title}\n")
            out.write("=" * 80 + "\n\n")
            out.write(clean_text + "\n\n")
            
    # Cleanup temp VTTs
    shutil.rmtree(temp_dir)
    return (final_file, total_files)

def main():
    parser = argparse.ArgumentParser(
        description="ytk - YouTube to Knowledge: Extract clean subtitles for RAG/LLMs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  ytknow https://youtube.com/@channel
  ytknow https://youtube.com/watch?v=video -l de
  ytknow https://youtube.com/@channel --survey
  ytknow [URL] -o ~/MyBase
        """
    )
    parser.add_argument("url", nargs="?", help="YouTube URL (Channel or Video)")
    parser.add_argument("-o", "--output", default=DEFAULT_OUTPUT_DIR, help="Output directory")
    parser.add_argument("-l", "--lang", help="Language code (e.g., 'en', 'de')")
    parser.add_argument("-s", "--survey", action="store_true", help="Survey channel/playlist for subtitle availability")
    parser.add_argument("--limit", type=int, default=50, help="Max videos to scan during survey (default: 50)")
    
    args = parser.parse_args()
    
    print_banner()
    
    url = args.url
    if not url:
        print(f"{Fore.YELLOW}No source provided.")
        url = input(f"{Fore.CYAN}👉 Enter YouTube URL (Channel or Video): ").strip()
    
    if not url:
        print(f"{Fore.RED}✗ No URL provided. Operation cancelled.")
        sys.exit(1)
    
    # Handle Survey mode
    if args.survey:
        run_channel_survey(url, limit=args.limit)
        sys.exit(0)

    is_channel = "@" in url or "/channel/" in url or "/user/" in url or "/c/" in url
    
    lang_code = args.lang
    if not lang_code:
        lang_code = select_language_interactive(url, is_channel)
        print("-" * 60)
        
    result = process_url(url, Path(args.output), lang_code)
    
    print("\n" + "=" * 60)
    if result:
        file_path, count = result
        print(f"{Fore.GREEN}✅ SUCCESS: Knowledge Base created!")
        print(f"{Fore.WHITE}Videos processed: {Fore.CYAN}{count}")
        print(f"{Fore.WHITE}Target File:      {Fore.GREEN}{file_path.absolute()}")
        print(f"{Fore.WHITE}File Size:        {Fore.YELLOW}{file_path.stat().st_size / 1024:.1f} KB")
    else:
        print(f"{Fore.RED}❌ FAILED: Could not create knowledge base.")
    
    print("=" * 60)
    print(f"{Fore.MAGENTA}✨ Thank you for using ytknow! ✨")

if __name__ == "__main__":
    main()
