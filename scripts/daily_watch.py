import feedparser
import yaml
import datetime
from dateutil import parser
import os
import google.generativeai as genai
import time

# 1. Configuration Gemini
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-1.5-flash')

def analyze_with_gemini(title, content):
    """Demande à Gemini si c'est intéressant pour un DevOps GCP"""
    try:
        prompt = f"""
        Agis comme un Senior Platform Engineer expert en Google Cloud.
        Analyse cette news :
        Titre: {title}
        Contenu: {content}

        Si c'est du marketing ou hors sujet (pas de lien avec GKE, Terraform, Vertex, Ops), réponds juste "SKIP".
        
        Si c'est technique et pertinent, réponds en français avec :
        1. Une phrase sur la nouveauté technique.
        2. Une phrase sur l'impact pour l'infra ou les coûts.
        """
        
        response = model.generate_content(prompt)
        time.sleep(1) 
        return response.text.strip()
    except Exception as e:
        return f"Erreur IA : {str(e)}"

# 2. Chargement Config
with open('config/interests.yaml', 'r') as f:
    config = yaml.safe_load(f)

found_articles = []
print("🚀 Démarrage de la veille Gemini...")

# 3. Parcours des flux
for feed in config['feeds']:
    try:
        d = feedparser.parse(feed['url'])
        print(f"Checking {feed['name']}...") # Log pour voir l'avancement
        
        for entry in d.entries:
            title = entry.title
            summary = entry.get('summary', '')
            link = entry.link
            
            # Gestion date (3 jours max)
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
                print(f"🔍 Analyse IA en cours : {title}")
                analysis = analyze_with_gemini(title, summary)
                
                if "SKIP" not in analysis:
                    found_articles.append({
                        'source': feed['name'],
                        'title': title,
                        'link': link,
                        'text': analysis
                    })
    except Exception as e:
        print(f"Erreur sur {feed['name']}: {e}")

# 4. Mise à jour du README
if found_articles:
    date = datetime.datetime.now().strftime('%d/%m/%Y')
    new_content = f"\n### 🇬 Veille du {date}\n\n"
    
    for art in found_articles:
        new_content += f"#### {art['title']} ({art['source']})\n"
        
        # --- CORRECTION ICI : On formate le texte AVANT de l'insérer ---
        # On remplace les sauts de ligne par des chevrons de citation Markdown
        formatted_text = art['text'].replace('\n', '\n> ')
        
        new_content += f"> {formatted_text}\n\n"
        new_content += f"[Lire l'article]({art['link']})\n---\n"
    
    if os.path.exists("README.md"):
        with open("README.md", "r") as f:
            old = f.read()
    else:
        old = "# Ma Veille Ops\n"
        
    with open("README.md", "w") as f:
        f.write("# Ma Veille Ops\n" + new_content + "\n" + old.replace("# Ma Veille Ops\n", ""))
    print("✅ Fini ! README mis à jour.")
else:
    print("Rien de nouveau.")