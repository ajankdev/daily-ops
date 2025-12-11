import feedparser
import yaml
import datetime
from dateutil import parser
import os
from groq import Groq
import time

# --- CONFIGURATION ---
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
HISTORY_FILE = "history.txt"

def load_history():
    if not os.path.exists(HISTORY_FILE):
        return set()
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f.readlines())

def save_history(urls):
    with open(HISTORY_FILE, "a", encoding="utf-8") as f:
        for url in urls:
            f.write(f"{url}\n")

def get_entry_date(entry):
    """
    Tries to extract the date from multiple standard RSS fields.
    GitHub Releases often use 'updated' instead of 'published'.
    """
    # List of potential date fields in order of priority
    date_fields = ['published', 'updated', 'created', 'date']
    
    for field in date_fields:
        date_str = entry.get(field)
        if date_str:
            try:
                dt = parser.parse(date_str)
                # Remove timezone info for comparison
                return dt.replace(tzinfo=None)
            except:
                continue
                
    # If absolutely no date is found, return None (do NOT default to now)
    return None

def analyze_with_groq(title, content):
    """
    Analyzes content using Llama 3.3 70B via Groq.
    """
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

    model_name = "llama-3.3-70b-versatile"
    
    try:
        chat_completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model=model_name,
            temperature=0.1,
        )
        return chat_completion.choices[0].message.content.strip()
    except Exception as e:
        if "429" in str(e):
            time.sleep(10)
            return "AI Error"
        print(f"    [!] Error: {str(e)}")
        return "AI Error"

# --- MAIN ENGINE ---
with open('config/interests.yaml', 'r') as f:
    config = yaml.safe_load(f)

processed_urls = load_history()
new_urls_to_save = []
found_articles = []

print("[*] Starting Daily Watch (Strict Date Mode)...")

for feed in config['feeds']:
    try:
        feed_name = feed['name'].strip()
        print(f"Checking {feed_name}...")
        
        d = feedparser.parse(feed['url'])
        
        # Limit to checking top 10 items (optimization)
        for entry in d.entries[:10]:
            title = entry.title
            link = entry.link
            
            # 1. Deduplication
            if link in processed_urls:
                continue

            # 2. STRICT DATE FILTER
            article_date = get_entry_date(entry)
            
            if article_date is None:
                # No date found? We skip it to avoid polluting with old stuff
                # Unless it's a very specific feed, it's better to miss one than have duplicates
                continue
                
            # Calculate age in days
            delta_days = (datetime.datetime.now() - article_date).days
            
            # If older than 3 days, SKIP.
            if delta_days > 3:
                # Debug log to ensure we know why we skip
                # print(f"  [Skip] Old article ({delta_days} days): {title[:30]}")
                continue

            # 3. Keyword Filter
            txt = (title + " " + entry.get('summary', '')).lower()
            keywords = config['filters']['must_include_one_of']
            
            if any(k.lower() in txt for k in keywords):
                if not any(ex.lower() in txt for ex in config['filters']['exclude']):
                    print(f"  [NEW] Analyzing ({delta_days}d ago): {title[:60]}...")
                    
                    analysis = analyze_with_groq(title, entry.get('summary', ''))
                    
                    new_urls_to_save.append(link)
                    processed_urls.add(link)
                    
                    if "SKIP" not in analysis and "AI Error" not in analysis:
                        found_articles.append({
                            'source': feed_name,
                            'title': title,
                            'link': link,
                            'text': analysis
                        })
                    
                    time.sleep(2)

    except Exception as e:
        print(f"Error feed {feed['name']}: {e}")

# Save History
if new_urls_to_save:
    save_history(new_urls_to_save)

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
    print("[-] No new relevant articles found today.")