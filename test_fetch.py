import urllib.request
import re

try:
    with urllib.request.urlopen('http://127.0.0.1:5000/watch/166613/ep-1') as response:
        html = response.read().decode('utf-8')
        match = re.search(r'<script id="episodeDataScript".*?>(.*?)</script>', html, re.DOTALL)
        if match:
            content = match.group(1).strip()
            print(f"FOUND SCRIPT TAG. Length: {len(content)}")
            print(f"Content prefix: {content[:200]}")
        else:
            print("SCRIPT TAG NOT FOUND")
            # Maybe check if word 'episodeDataScript' is in html at all
            if 'episodeDataScript' in html:
                print("But 'episodeDataScript' string is present in html.")
            else:
                print("'episodeDataScript' string is entirely missing from html.")
except Exception as e:
    print(f"Error: {e}")
