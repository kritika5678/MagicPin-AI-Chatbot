#!/usr/bin/env python3
"""
Wrapper for judge_simulator.py — does NOT modify the original file.
 
Groq's API (and OpenAI's/Gemini's) sit behind Cloudflare, which sometimes
blocks the default Python urllib User-Agent ("Python-urllib/3.x") with a 403,
even though the same request works fine from curl or a browser.
 
This wrapper installs a custom global urllib opener with a normal browser
User-Agent BEFORE judge_simulator.py runs, then executes judge_simulator.py
exactly as-is. No lines in judge_simulator.py are changed.
 
USAGE:
    python run_judge_patched.py
(instead of "python judge_simulator.py")
"""
 
import urllib.request
from pathlib import Path
 
# Install a global opener with a normal browser User-Agent.
# urllib only adds this header if the request doesn't already set one,
# so this has zero effect on any other header/behavior in the script.
opener = urllib.request.build_opener()
opener.addheaders = [
    ("User-agent",
     "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
     "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
]
urllib.request.install_opener(opener)
 
# Run judge_simulator.py's code, unmodified, in this same process.
script_path = Path(__file__).parent / "judge_simulator.py"
source = script_path.read_text(encoding="utf-8")
exec(
    compile(source, str(script_path), "exec"),
    {"__name__": "__main__", "__file__": str(script_path)}
)