import feedparser
import yaml
import datetime
from dateutil import parser
import os

# 1. Charger la config
with open('config/interests.yaml', 'r') as f:
    config = yaml.safe_load(f)

found_articles = []

# 2. Parcourir les flux RSS
print("🔍 Recherche d'articles...")
for feed in config['feeds']:
    try:
        d = feedparser.parse(feed['url'])
        print(f"  Checking {feed['name']}...")
        
        for entry in d.entries:
            # Récupération titre + résumé
            title = entry.title
            summary = entry.get('summary', '') or entry.get('description', '')
            link = entry.link
            
            # Gestion de la date (ignorer articles de + de 48h)
            try:
                published = parser.parse(entry.get('published', entry.get('updated', str(datetime.datetime.now()))))
                # Convertir en timezone naive pour comparaison simple
                published = published.replace(tzinfo=None)
                if (datetime.datetime.now() - published).days > 2:
                    continue
            except:
                continue # Skip si pas de date
            
            content_to_check = (title + " " + summary).lower()
            
            # 3. Filtrage (Logique Platform Engineer)
            # Doit contenir au moins un mot clé
            if any(k.lower() in content_to_check for k in config['filters']['must_include_one_of']):
                # Ne doit PAS contenir de mot exclu
                if not any(ex.lower() in content_to_check for ex in config['filters']['exclude']):
                    found_articles.append({
                        'source': feed['name'],
                        'title': title,
                        'link': link,
                        'date': published.strftime("%Y-%m-%d")
                    })
    except Exception as e:
        print(f"Erreur sur {feed['name']}: {e}")

# 4. Générer le Markdown
print(f"✅ {len(found_articles)} articles pertinents trouvés.")

if found_articles:
    # Trier par date
    found_articles.sort(key=lambda x: x['date'], reverse=True)
    
    new_content = f"\n### 📅 Veille du {datetime.datetime.now().strftime('%d/%m/%Y')}\n\n"
    for art in found_articles:
        new_content += f"- **[{art['source']}]** [{art['title']}]({art['link']})\n"
    
    # Lire le README actuel
    if os.path.exists("README.md"):
        with open("README.md", "r") as f:
            current_content = f.read()
    else:
        current_content = "# Ma Veille IA & Platform Ops\n\n"
        
    # Insérer en haut (après le titre)
    header = "# Ma Veille IA & Platform Ops\n"
    if header in current_content:
        updated_content = current_content.replace(header, header + new_content)
    else:
        updated_content = header + new_content + "\n" + current_content

    # Sauvegarder
    with open("README.md", "w") as f:
        f.write(updated_content)
else:
    print("Rien de nouveau aujourd'hui.")
