import os
from pathlib import Path
from .config import Fore

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
