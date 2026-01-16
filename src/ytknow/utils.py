import sys
import shutil
import logging
import termios
import tty
from pathlib import Path
from .config import LOG_FILE, Fore, Style

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

def print_progress(current, total, prefix='', suffix='', length=40):
    """Prints a custom progress bar."""
    percent = ("{0:.1f}").format(100 * (current / float(total)))
    filled_length = int(length * current // total)
    bar = '█' * filled_length + '-' * (length - filled_length)
    # \033[K clears from cursor to end of line
    sys.stdout.write(f'\r{prefix} |{bar}| {percent}% {suffix}\033[K')
    sys.stdout.flush()

def get_key():
    """Reads a single keypress from stdin (cross-platform-ish, focusing on Mac/Linux)."""
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(sys.stdin.fileno())
        ch = sys.stdin.read(1)
        if ch == '\x1b': # Handle arrows
            ch += sys.stdin.read(2)
        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
