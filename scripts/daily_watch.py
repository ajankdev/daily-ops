import feedparser
import yaml
import datetime
from dateutil import parser
import os
from google import genai
import time

# --- CONFIGURATION (SDK 2025) ---
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

def analyze_with_gemini(title, content):
    """
    Analyzes content using Gemini 2.0/1.5 with robust Rate Limit handling.
    """
    # Dynamic Date Context: "December 2025", "January 2026", etc.
    current_context = datetime.datetime.now().strftime('%B %Y')

    prompt = f"""
    Act as a Staff Platform Engineer (GCP/K8s/AI) working in {current_context}.
    Analyze this input (Title: "{title}") and classify it into one of my specific interest areas:

    1. [GCP_K8S_CORE]: GKE, Autopilot, Cloud Run, CNCF Ecosystem.
    2. [OPS_STACK]: Terraform/IaC, FluxCD/GitOps, Renovate.
    3. [AI_INFRA]: vLLM, Ray, NVIDIA GPUs, MCP, RAG, Vector DBs.
    4. [AI_MODELS]: Anthropic (Claude), OpenAI, Meta (Llama), Google (Gemini).
    5. [OBS_SEC]: Datadog/OTel, SRE, Cloud Security.

    INSTRUCTIONS:
    - FILTERING: If generic/marketing/irrelevant: Reply "SKIP".
    - ANALYSIS: If relevant, map to category.
    
    Reply STRICTLY format:
    **Category:** [TAG]
    **Summary:** <Technical summary>
    **Impact:** <Ops Impact>
    
    Input Content:
    {content}
    """

    # MODEL PRIORITY LIST
    # 1. gemini-2.0-flash-exp : SOTA.
    # 2. gemini-1.5-flash : Stable fallback.
    models = ['gemini-2.0-flash-exp', 'gemini-1.5-flash']
    
    for model_name in models:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt
            )
            return response.text.strip()
            
        except Exception as e:
            error_msg = str(e)
            
            # Handle Rate Limits (429)
            if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
                print(f"    [!] Quota (429) on {model_name}. Sleeping 30s...")
                time.sleep(30)
                try:
                    print(f"    [R] Retry {model_name}...")
                    response = client.models.generate_content(
                        model=model_name,
                        contents=prompt
                    )
                    return response.text.strip()
                except:
                    pass # Failover to next model
            
            print(f"    [!] Error on {model_name}: {error_msg}")
            continue
            
    return "AI Error: All models failed."

# --- MAIN ENGINE ---
with open('config/interests.yaml', 'r') as f:
    config = yaml.safe_load(f)

found_articles = []
print("[*] Starting Daily Watch...")

for feed in config['feeds']:
    try:
        # Feed name clean up
        feed_name = feed['name'].strip()
        print(f"Checking {feed_name}...")
        
        d = feedparser.parse(feed['url'])
        
        for entry in d.entries:
            title = entry.title
            summary = entry.get('summary', '')
            link = entry.link
            
            try:
                published = parser.parse(entry.get('published', str(datetime.datetime.now())))
                published = published.replace(tzinfo=None)
                if (datetime.datetime.now() - published).days > 3:
                    continue
            except:
                continue

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
                    
                    # Pause indispensable pour l'API
                    time.sleep(10)

    except Exception as e:
        print(f"Error feed {feed['name']}: {e}")

# --- DOCUMENT GENERATION ---
if found_articles:
    current_date = datetime.datetime.now().strftime('%Y-%m-%d')
    markdown_content = f"# Daily Digest: {current_date}\n\n"
    
    for art in found_articles:
        markdown_content += f"### {art['title']}\n"
        markdown_content += f"**Source:** {art['source']}\n\n"
        clean_text = art['text'].replace('\n', '\n> ')
        markdown_content += f"> {clean_text}\n\n"
        markdown_content += f"[Read Article]({art['link']})\n\n"
        markdown_content += "---\n"

    os.makedirs("archives", exist_ok=True)
    archive_filename = f"archives/{current_date}.md"
    
    with open(archive_filename, "w", encoding="utf-8") as f:
        f.write(markdown_content)
    print(f"[+] Archive created: {archive_filename}")

    readme_header = f"""# Platform & AI Watch

**Last Update:** {current_date}

## Today's Highlights
"""
    history_section = "\n## Recent History\n"
    try:
        archive_files = sorted([f for f in os.listdir("archives") if f.endswith(".md")], reverse=True)
        for filename in archive_files[:10]: 
            date_label = filename.replace(".md", "")
            if date_label != current_date:
                history_section += f"- [{date_label}](archives/{filename})\n"
    except:
        history_section = ""

    full_readme = readme_header + "\n" + markdown_content.replace("# Daily Digest:", "").strip() + "\n" + history_section
    
    with open("README.md", "w", encoding="utf-8") as f:
        f.write(full_readme)
    print("[+] README updated.")
else:
    print("[-] No relevant news found today.")