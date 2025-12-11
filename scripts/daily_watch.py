import feedparser
import yaml
import datetime
from dateutil import parser
import os
from google import genai # Nouvelle importation SDK 2025
import time

# 1. Configuration Client (Nouvelle syntaxe SDK)
# Le client récupère automatiquement GEMINI_API_KEY dans l'environnement
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

def analyze_with_gemini(title, content):
    """
    Utilise Gemini 2.5 Flash (Standard 2025)
    """
    prompt = f"""
    Agis comme un Senior Platform Engineer (GCP/GKE).
    Analyse cette news :
    Titre: {title}
    Contenu: {content}

    Réponds STRICTEMENT sous ce format :
    - Si c'est du marketing/hors sujet : Réponds juste "SKIP"
    - Si c'est pertinent (Infra, Kubernetes, AI Ops) :
      1. Résumé technique en 1 phrase.
      2. Impact opérationnel (Coût/Perf/Maintenance).
    """

    # Liste de priorité des modèles pour 2025
    # On commence par le 2.5 Flash (le standard actuel)
    models_to_try = ['gemini-2.5-flash', 'gemini-2.0-flash', 'gemini-1.5-flash']
    
    for model_name in models_to_try:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt
            )
            return response.text.strip()
        except Exception as e:
            print(f"    ⚠️ {model_name} non dispo, essai suivant... ({e})")
            continue
            
    return "Erreur IA : Tous les modèles ont échoué."

# --- LE REST DU SCRIPT (MOTEUR DE VEILLE) ---
with open('config/interests.yaml', 'r') as f:
    config = yaml.safe_load(f)

found_articles = []
print("🚀 Démarrage de la veille (SDK google-genai / Gemini 2.5)...")

for feed in config['feeds']:
    try:
        d = feedparser.parse(feed['url'])
        print(f"Checking {feed['name']}...")
        
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
                print(f"🔍 Analyse IA : {title}")
                analysis = analyze_with_gemini(title, summary)
                
                if "SKIP" not in analysis and "Erreur IA" not in analysis:
                    found_articles.append({
                        'source': feed['name'],
                        'title': title,
                        'link': link,
                        'text': analysis
                    })

    except Exception as e:
        print(f"Erreur flux {feed['name']}: {e}")

if found_articles:
    date = datetime.datetime.now().strftime('%d/%m/%Y')
    new_content = f"\n### 🇬 Veille Gemini 2.5 du {date}\n\n"
    
    for art in found_articles:
        new_content += f"#### {art['title']} ({art['source']})\n"
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
    print("✅ README mis à jour.")
else:
    print("Rien de nouveau.")