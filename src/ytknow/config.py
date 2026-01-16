import sys
try:
    from colorama import init, Fore, Style
    init(autoreset=True)
except ImportError:
    class FakeColor:
        def __getattr__(self, name):
            return ""
    Fore = Style = FakeColor()

# Configuration
LOG_FILE = "conversion.log"
DEFAULT_OUTPUT_DIR = "outputs"

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
