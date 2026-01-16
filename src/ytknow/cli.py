import sys
import shutil
import argparse
from pathlib import Path
from .config import DEFAULT_OUTPUT_DIR, Fore, Style, get_native_name, print_banner
from .utils import get_key
from .core import run_channel_survey, process_url, get_available_languages

def select_language_interactive(url: str, is_channel: bool) -> str:
    """Shows an interactive TUI to select a language."""
    available = get_available_languages(url, is_channel)
    
    if not available:
        print(f"{Fore.YELLOW}⚠ No subtitles found via metadata check.")
        print(f"{Fore.WHITE}Defaulting to 'en' (or use --lang code to override).")
        return "en"
    
    # Sort: manual first, then auto
    # manual tuples: (code-orig, name, [Original])
    # auto tuples: (code, name, [Auto])
    manual = sorted([x for x in available if "Original" in x[2]], key=lambda x: x[0])
    auto = sorted([x for x in available if "Auto" in x[2]], key=lambda x: x[0])
    
    all_options = [x[0] for x in manual] + [x[0] for x in auto]
    display_info = {x[0]: (x[1], x[2]) for x in available}
    
    # If only one option, pick it
    if len(all_options) == 1:
        print(f"{Fore.GREEN}✓ Auto-selected only available language: {all_options[0]}")
        return all_options[0]

    current_idx = 0
    selected_idx = 0
    
    print(f"{Fore.WHITE}Use UP/DOWN arrows to select, ENTER to confirm:")
    print(f"{Fore.CYAN}(Many options are on-the-fly 'Auto-Translations' by YouTube)")
    
    # Simple TUI loop
    while True:
        # Hide cursor
        sys.stdout.write("\033[?25l")
        
        # Calculate window to show (e.g., 10 items around selection)
        window_size = 15
        start_idx = max(0, selected_idx - window_size // 2)
        end_idx = min(len(all_options), start_idx + window_size)
        
        # Adjust start if near end
        if end_idx - start_idx < window_size:
            start_idx = max(0, end_idx - window_size)

        for i in range(start_idx, end_idx):
            code = all_options[i]
            description, tag = display_info.get(code, (code, ""))
            native = get_native_name(code)
            native_str = f"({native})" if native else ""
            
            # Highlight selected
            if i == selected_idx:
                line = f"{Fore.GREEN}➔ {code:<10} {native_str:<20} {tag}"
            else:
                line = f"  {code:<10} {native_str:<20} {tag}"
            
            # Clear line and print
            sys.stdout.write(f"\r{line}\033[K\n")
            
        if end_idx < len(all_options):
             sys.stdout.write(f"  ... and {len(all_options) - end_idx} more\033[K\n")
             extra_lines = 1
        else:
             extra_lines = 0

        # Wait for input
        key = get_key()
        
        # Move cursor back up
        total_printed_lines = (end_idx - start_idx) + extra_lines
        
        if key == '\x1b[A': # UP
            selected_idx = (selected_idx - 1) % len(all_options)
        elif key == '\x1b[B': # DOWN
            selected_idx = (selected_idx + 1) % len(all_options)
        elif key in ['\r', '\n']: # ENTER
            # Restore cursor down
            sys.stdout.write(f"\033[{total_printed_lines}B")
            break
        elif key == '\x03': # Ctrl+C
            sys.stdout.write("\033[?25h") # Show cursor
            sys.exit(0)
            
        # Move cursor back up for next frame
        sys.stdout.write(f"\033[{total_printed_lines}A")

    sys.stdout.write("\033[?25h") # Show cursor
    print(f"\n{Fore.GREEN}✓ Selected: {all_options[selected_idx]}")
    return all_options[selected_idx]

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
    
    # AI Args
    parser.add_argument("--summarize", action="store_true", help="Generate AI summary (requires OPENAI_API_KEY)")
    parser.add_argument("--model", default="base", help="Whisper model size (tiny, base, small, medium, large) for fallback")
    
    args = parser.parse_args()
    
    print_banner()
    
    url = args.url
    if not url:
        print(f"{Fore.YELLOW}No source provided.")
        try:
            url = input(f"{Fore.CYAN}👉 Enter YouTube URL (Channel or Video): ").strip()
        except KeyboardInterrupt:
             print("\nCancelled.")
             sys.exit(0)
    
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
        try:
            total_size = sum(f.stat().st_size for f in dir_path.glob('*') if f.is_file())
            print(f"{Fore.WHITE}Total Size:       {Fore.YELLOW}{total_size / 1024:.1f} KB")
        except Exception:
            pass
            
        if args.summarize:
             print(f"{Fore.MAGENTA}🧠 Summaries generated in output folder.")
             
    else:
        print(f"{Fore.RED}❌ FAILED: Could not create knowledge base.")
    
    print("=" * 60)
    print(f"{Fore.MAGENTA}✨ Thank you for using ytknow! ✨")
