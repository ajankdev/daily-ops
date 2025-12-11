import feedparser
import yaml
import datetime
from dateutil import parser
import os
from google import genai
from google.genai import types
import time

# Configuration Gemini
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

def analyze_with_gemini(title, content):
    """
    Analyzes content with robust Rate Limit handling (Backoff strategy).
    """
    prompt = f"""
    Act as a Senior Platform Engineer (GCP/Kubernetes).
    Analyze this news item:
    Title: {title}
    Content: {content}

    Reply STRICTLY using this format:
    - If marketing/irrelevant: Reply "SKIP"
    - If relevant (Tech, Infra, AI Ops):
      1. Technical summary (1 sentence).
      2. Operational impact (Cost/Performance).
    """

    # We try models. Note: 'gemini-1.5-flash' is often more generous with quotas than 2.0
    models = ['gemini-2.5-flash', 'gemini-1.5-flash', 'gemini-1.5-pro']
    
    for model_name in models:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt
            )
            return response.text.strip()
            
        except Exception as e:
            error_msg = str(e)
            # Detect Rate Limit (429) or Overloaded model (503)
            if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg or "Too Many Requests" in error_msg:
                print(f"    [!] Quota exceeded (429) on {model_name}. Sleeping 30s...")
                time.sleep(30) # Aggressive wait for Free Tier refill
                
                try:
                    print(f"    [R] Retrying {model_name}...")
                    response = client.models.generate_content(model=model_name, contents=prompt)
                    return response.text.strip()
                except Exception as e2:
                    print(f"    [X] Retry failed. Moving to next model.")
                    continue 
            
            print(f"    [!] Error on {model_name}: {error_msg}")
            continue
            
    return "AI Error: All models failed or rate limited."

# --- MAIN ENGINE ---
with open('config/interests.yaml', 'r') as f:
    config = yaml.safe_load(f)

found_articles = []
print("[*] Starting Daily Watch (Rate-Limit Safe Mode)...")

for feed in config['feeds']:
    try:
        # Clean feed name (remove emojis for logs if any remain)
        feed_name = feed['name'].encode('ascii', 'ignore').decode('ascii').strip()
        print(f"Checking {feed_name}...")
        
        d = feedparser.parse(feed['url'])
        
        for entry in d.entries:
            title = entry.title
            summary = entry.get('summary', '')
            link = entry.link
            
            # Date Filter (3 days)
            try:
                published = parser.parse(entry.get('published', str(datetime.datetime.now())))
                published = published.replace(tzinfo=None)
                if (datetime.datetime.now() - published).days > 3:
                    continue
            except:
                continue

            # Keyword Filter
            txt = (title + " " + summary).lower()
            keywords = config['filters']['must_include_one_of']
            
            if any(k.lower() in txt for k in keywords):
                if not any(ex.lower() in txt for ex in config['filters']['exclude']):
                    print(f"  [>] Analyzing: {title[:60]}...")
                    
                    analysis = analyze_with_gemini(title, summary)
                    
                    if "SKIP" not in analysis and "AI Error" not in analysis:
                        found_articles.append({
                            'source': feed_name,
                            'title': title,
                            'link': link,
                            'text': analysis
                        })
                    
                    # SYSTEMATIC PAUSE
                    # Even on success, we wait 10s to respect the RPM (Requests Per Minute) limit
                    # of the Free Tier.
                    time.sleep(10)

    except Exception as e:
        print(f"Error processing feed {feed['name']}: {e}")

# --- README GENERATION ---
if found_articles:
    date = datetime.datetime.now().strftime('%Y-%m-%d')
    new_content = f"\n### Daily Digest: {date}\n\n"
    
    for art in found_articles:
        new_content += f"#### {art['title']} ({art['source']})\n"
        clean_text = art['text'].replace('\n', '\n> ')
        new_content += f"> {clean_text}\n\n"
        new_content += f"[Read Article]({art['link']})\n---\n"
    
    if os.path.exists("README.md"):
        with open("README.md", "r") as f:
            old = f.read()
    else:
        old = "# Platform & AI Watch\n"
        
    with open("README.md", "w") as f:
        f.write("# Platform & AI Watch\n" + new_content + "\n" + old.replace("# Platform & AI Watch\n", ""))
    print("[+] README updated successfully.")
else:
    print("[-] No relevant news found today.")