import re
import textwrap
from html import unescape
from typing import List

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
