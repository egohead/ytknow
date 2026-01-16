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
import json
import textwrap
from collections import Counter
from typing import List, Dict, Optional

try:
    from colorama import init, Fore, Style
    init(autoreset=True)
except ImportError:
    # Fallback if colorama is not installed yet
    class FakeColor:
        def __getattr__(self, name):
            return ""
    Fore = Style = FakeColor()

# Optional Imports (Lazy Loaded where possible, but top-level import for typing is fine)
try:
    import openai
except ImportError:
    openai = None

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
    'ne': 'नेपाली', 'nl': 'Nederlands', 'no': 'Norsk', 'ny': 'Chichewa', 'or': 'ଓଡ଼ିଆ',
    'pa': 'ਪੰਜਾਬੀ', 'pl': 'Polski', 'ps': 'پښتو', 'pt': 'Português', 'qu': 'Quechua',
    'ro': 'Română', 'ru': 'Русский', 'rw': 'Kinyarwanda', 'sd': 'سنڌੀ', 'si': 'සිංහල',
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
        if result.stdout.strip():
            title = result.stdout.strip().splitlines()[0]
            return re.sub(r'[^\w\-]', '_', title)
        return "Unknown_Source"
    except Exception as e:
        handle_ytdlp_error(e, "get_source_title")
        # Fallback to URL-based slug if metadata fetching fails
        return re.sub(r'[^\w\-]', '_', url.split('@')[-1] if '@' in url else "knowledge")

# --- AI Features ---

def transcribe_with_whisper(audio_path: Path, model_name: str = "base") -> str:
    """Transcribes an audio file using OpenAI Whisper (local)."""
    print(f"\n{Fore.MAGENTA}🎙️  Subtitles missing. Starting fallback transcription with Whisper ({model_name})...")
    print(f"{Fore.WHITE}   Using device: CPU/MPS (MacOS). This takes 1-5 mins per 10 mins of audio.")
    
    try:
        import whisper
        import warnings
        # Filter warnings to keep output clean
        warnings.filterwarnings("ignore")
        
        model = whisper.load_model(model_name)
        result = model.transcribe(str(audio_path), fp16=False) # fp16=False often needed on CPU/MPS
        
        text = result["text"].strip()
        print(f"{Fore.GREEN}✓ Transcription complete! ({len(text)} chars)")
        return text
    except ImportError:
        print(f"{Fore.RED}✗ Whisper not installed. Run 'pip install openai-whisper'.")
        return ""
    except Exception as e:
        print(f"Error during transcription: {e}")
        return ""

def generate_summary_llm(text: str, metadata: dict) -> str:
    """Generates a summary using OpenAI API."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print(f"{Fore.YELLOW}⚠ Summary requested but OPENAI_API_KEY not found in environment.")
        return ""

    if not text or len(text) < 50:
        return ""

    print(f"\n{Fore.MAGENTA}🧠 Generating AI Summary (gpt-4o-mini)...")
    
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        
        prompt = f"""
        You are an expert summarizer. Analyze the following video transcript.
        
        Video Title: {metadata.get('title', 'Unknown')}
        Channel: {metadata.get('channel', 'Unknown')}
        
        Please provide:
        1. A comprehensive 2-3 paragraph Summary of the content.
        2. A list of 5-10 Key Takeaways (bullet points).
        3. If possible, crude timestamps for major topic shifts (based on text flow).
        
        Format output in Markdown.
        
        Transcript:
        {text[:25000]} 
        """ 
        # Truncate to ~25k chars to stay safe within context windows of smaller models if used, 
        # though gpt-4o-mini has 128k context, so we could send more. 
        # 25k chars is roughly 30-45 mins of talking.

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that summarizes video transcripts."},
                {"role": "user", "content": prompt}
            ]
        )
        
        return response.choices[0].message.content
    except Exception as e:
        print(f"{Fore.RED}✗ Summarization failed: {e}")
        return ""

# --- End AI Features ---


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
    
    # Smart Fallback: If 'en' is requested but not found, try 'en-orig'
    if "en" not in langs and "en-orig" in langs:
        return "en-orig"
        
    # If only one option exists, take it (if it's English-ish)
    if len(langs) == 1 and "en" in langs[0]:
        return langs[0]
    
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

def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 100) -> List[str]:
    """Splits text into overlapping chunks, respecting sentence boundaries where possible."""
    if not text:
        return []
        
    chunks = []
    start = 0
    text_len = len(text)
    
    while start < text_len:
        end = start + chunk_size
        
        # If we are strictly inside the text (not at the very end)
        if end < text_len:
            # Look for the last period/newline in the chunk to break cleanly
            # We look back up to 30% of the chunk size
            lookback = int(chunk_size * 0.3)
            split_point = -1
            
            # Try to find a sentence ending
            for i in range(end, end - lookback, -1):
                if text[i] in ['.', '!', '?', '\n']:
                    split_point = i + 1
                    break
            
            if split_point != -1:
                end = split_point
        
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
            
        # Move start forward, keeping the overlap
        # If we successfully split at a sentence, we don't necessarily need overlap 
        # if the context is preserved, but for RAG overlap is usually safer.
        start = end - overlap
        
        # Ensure we always move forward
        if start >= end:
            start = end
            
    return chunks

def process_url(url: str, output_dir: Path, lang_code: str, enable_summarize: bool = False, whisper_model: str = "base") -> Optional[tuple]:
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
    
    # yt-dlp command to get subtitles AND metadata
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
           # "--progress-template", "DOWNLOAD_PROGRESS:%(progress._percent_str)s", # Skip for simplicity in fallback
            "--ignore-errors",
            url            
        ]
        try:
             subprocess.run(audio_cmd, check=True)
        except Exception as e:
             print(f"{Fore.RED}✗ Audio download failed: {e}")
             return None

        # 2. Transcribe
        audio_files = list(temp_dir.glob("*.m4a"))
        if not audio_files:
             print(f"{Fore.RED}✗ No audio files downloaded.")
             return None
             
        # Generate pseudo-VTTs or just handle text directly. 
        # For compatibility with loop below, we will iterate audio files and transcribe them on the fly
        # instead of vtt_files.
    # --- End Whisper Logic setup --

    # Determine what files to process (VTTs or Audio Fallback)
    files_to_process = vtt_files
    is_audio_fallback = False
    
    if not vtt_files:
        files_to_process = list(temp_dir.glob("*.m4a"))
        is_audio_fallback = True
        
    if not files_to_process:
        print(f"{Fore.RED}❌ No content found to process.")
        shutil.rmtree(temp_dir)
        return None

    # Prepare the output directory for this session
    session_dir = output_dir / f"{source_slug}_{lang_code}"
    session_dir.mkdir(exist_ok=True)
    
    jsonl_master = session_dir / "knowledge_master.jsonl"
    jsonl_chunks = session_dir / "knowledge_chunks.jsonl"
    
    total_files = len(files_to_process)
    print(f"{Fore.WHITE}Step 2/3: Processing {total_files} videos into '{session_dir.name}/'...")
    
    import json
    processed_count = 0
    with open(jsonl_master, "w", encoding="utf-8") as j_master, \
         open(jsonl_chunks, "w", encoding="utf-8") as j_chunks:
         
        for i, file_path in enumerate(files_to_process, 1):
            # Base name for metadata matching
            # VTT: .lang.vtt -> base  | Audio: .m4a -> base
            base_name = file_path.stem
            # Clean up suffix like .en or .de if it exists (for vtt)
            base_name = re.sub(r'\.[a-z]{2}(-[a-zA-Z0-9]+)?$', '', base_name)
            
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
                
                if is_audio_fallback:
                    # TRANSCRIBE
                    clean_text = transcribe_with_whisper(file_path, model_name=whisper_model)
                else:
                    # READ VTT
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    clean_text = clean_vtt_content(content)
                
                if clean_text:
                    video_title = metadata.get("title") or base_name
                    safe_title = re.sub(r'[^\w\-]', '_', video_title)[:100]
                    target_file = session_dir / f"{safe_title}.txt"
                    
                    # 1. Save TXT with Full Metadata Context
                    with open(target_file, "w", encoding="utf-8") as f:
                        f.write(f"TITLE: {video_title}\n")
                        if metadata.get("url"): f.write(f"URL:   {metadata['url']}\n")
                        if metadata.get("date"): f.write(f"DATE:  {metadata['date']}\n")
                        if metadata.get("description"):
                            f.write(f"DESCRIPTION:\n{textwrap.indent(metadata['description'][:500] + '...', '  ')}\n")
                        f.write("-" * 60 + "\n\n")
                        f.write(clean_text + "\n")
                    
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
                             summary_file = session_dir / f"{safe_title}_summary.md"
                             with open(summary_file, "w", encoding="utf-8") as f:
                                 f.write(summary)
                             # Append summary as a special chunk or separate file? 
                             # For now, just a separate file.
                    
                    processed_count += 1
            except Exception as e:
                logger.error(f"Failed to process {file_path.name}: {e}")
            
    # Cleanup temp folder
    shutil.rmtree(temp_dir)
    return (session_dir, processed_count)

def main():
    parser = argparse.ArgumentParser(
        description="ytk - YouTube to Knowledge: Extract clean subtitles for RAG/LLMs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  ytknow https://youtube.com/@channel
  ytknow https://youtube.com/watch?v=video -l de
  ytknow https://youtube.com/watch?v=video --summarize
  ytknow [URL] -o ~/MyBase --model small
        """
    )
    parser.add_argument("url", nargs="?", help="YouTube URL (Channel or Video)")
    parser.add_argument("-o", "--output", default=DEFAULT_OUTPUT_DIR, help="Output directory")
    parser.add_argument("-l", "--lang", help="Language code (e.g., 'en', 'de')")
    parser.add_argument("-s", "--survey", action="store_true", help="Survey channel/playlist for subtitle availability")
    parser.add_argument("--limit", type=int, default=50, help="Max videos to scan during survey (default: 50)")
    
    # New AI Args
    parser.add_argument("--summarize", action="store_true", help="Generate AI summary (requires OPENAI_API_KEY)")
    parser.add_argument("--model", default="base", help="Whisper model size (tiny, base, small, medium, large) for fallback")
    
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
        
    result = process_url(url, Path(args.output), lang_code, enable_summarize=args.summarize, whisper_model=args.model)
    
    print("\n" + "=" * 60)
    if result:
        dir_path, count = result
        print(f"{Fore.GREEN}✅ SUCCESS: Knowledge Base created!")
        print(f"{Fore.WHITE}Videos processed: {Fore.CYAN}{count}")
        print(f"{Fore.WHITE}Location:         {Fore.GREEN}{dir_path.absolute()}")
        
        # Calculate total size of the session directory
        total_size = sum(f.stat().st_size for f in dir_path.glob('*') if f.is_file())
        print(f"{Fore.WHITE}Total Size:       {Fore.YELLOW}{total_size / 1024:.1f} KB")
        
        if args.summarize:
             print(f"{Fore.MAGENTA}🧠 Summaries generated in output folder.")
             
    else:
        print(f"{Fore.RED}❌ FAILED: Could not create knowledge base.")
    
    print("=" * 60)
    print(f"{Fore.MAGENTA}✨ Thank you for using ytknow! ✨")

if __name__ == "__main__":
    main()
