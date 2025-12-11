import feedparser
import yaml
import datetime
from dateutil import parser
import os
import google.generativeai as genai
import time

# 1. On se connecte à Gemini avec la clé cachée dans GitHub
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
        
        # On demande à l'IA
        response = model.generate_content(prompt)
        time.sleep(1) # Petite pause pour être gentil avec l'API gratuite
        return response.text.strip()
    except Exception as e:
        return f"Erreur IA : {str(e)}"

# 2. On charge ta configuration
with open('config/interests.yaml', 'r') as f:
    config = yaml.safe_load(f)

found_articles = []
print("🚀 Démarrage de la veille Gemini...")

# 3. On parcours tes liens RSS
for feed in config['feeds']:
    try:
        d = feedparser.parse(feed['url'])
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

            # Vérification simple des mots clés
            txt = (title + " " + summary).lower()
            keywords = config['filters']['must_include_one_of']
            
            if any(k.lower() in txt for k in keywords):
                print(f"🔍 Analyse IA en cours : {title}")
                analysis = analyze_with_gemini(title, summary)
                
                # Si Gemini ne dit pas SKIP, on garde !
                if "SKIP" not in analysis:
                    found_articles.append({
                        'source': feed['name'],
                        'title': title,
                        'link': link,
                        'text': analysis
                    })
    except Exception as e:
        print(f"Erreur sur {feed['name']}")

# 4. On met à jour le README
if found_articles:
    date = datetime.datetime.now().strftime('%d/%m/%Y')
    new_content = f"\n### 🇬 Veille du {date}\n\n"
    
    for art in found_articles:
        new_content += f"#### {art['title']} ({art['source']})\n"
        new_content += f"> {art['text'].replace(chr(10), '\n> ')}\n\n"
        new_content += f"[Lire l'article]({art['link']})\n---\n"
    
    if os.path.exists("README.md"):
        with open("README.md", "r") as f:
            old = f.read()
    else:
        old = "# Ma Veille Ops\n"
        
    with open("README.md", "w") as f:
        f.write("# Ma Veille Ops\n" + new_content + "\n" + old.replace("# Ma Veille Ops\n", ""))
    print("✅ Fini !")
else:
    print("Rien de nouveau.")
