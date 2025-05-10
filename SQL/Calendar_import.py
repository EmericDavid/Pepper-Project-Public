import sqlite3
from icalendar import Calendar
import os
import re


def import_calendars(file_list):
    """
    Importe une liste de fichiers iCalendar dans la base de données SQLite.
    Extrait les informations détaillées comme la matière et les promotions (TD).
    
    Args:
        file_list (list): Liste des chemins des fichiers iCalendar à importer
    """
    # Créer une base SQLite
    conn = sqlite3.connect("./SQL/calendar.db")
    cursor = conn.cursor()
    
    # Supprimer la table si elle existe
    cursor.execute("DROP TABLE IF EXISTS events")
    
    # Créer la table avec les colonnes supplémentaires
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS events (
        uid TEXT PRIMARY KEY,
        dtstart TEXT,
        dtend TEXT,
        summary TEXT,
        description TEXT,
        location TEXT,
        categories TEXT,
        matiere TEXT,
        enseignant TEXT,
        promotions TEXT,
        memo TEXT
    )
    """)
    
    total_events = 0
    
    # Traiter chaque fichier de la liste
    for ical_file in file_list:
        if not os.path.exists(ical_file):
            print(f"Le fichier {ical_file} n'existe pas. Ignoré.")
            continue
            
        print(f"Importation du fichier: {ical_file}")
        
        # Lire et parser le fichier iCalendar
        try:
            with open(ical_file, 'r', encoding='utf-8') as f:
                cal = Calendar.from_ical(f.read())
                
                event_count = 0
                for component in cal.walk():
                    if component.name == "VEVENT":
                        uid = component.get("UID")
                        dtstart = component.get("DTSTART").dt
                        dtend = component.get("DTEND").dt
                        summary = component.get("SUMMARY")
                        description = component.get("DESCRIPTION")
                        location = component.get("LOCATION")
                        
                        # Extraire les informations spécifiques de la description
                        matiere = ""
                        enseignant = ""
                        promotions = ""
                        memo = ""
                        
                        if description:
                            # Utiliser des expressions régulières pour extraire les informations
                            matiere_match = re.search(r"Matière : ([^\n]+)", description)
                            if matiere_match:
                                matiere = matiere_match.group(1)
                                
                            enseignant_match = re.search(r"Enseignant : ([^\n]+)", description)
                            if enseignant_match:
                                enseignant = enseignant_match.group(1)
                                
                            
                            #check the promotion in the UID (eg : Cours-60551-41-M1-IA-CLA-Index-Education -> M1-IA-CLA)
                            promotions_match = re.search(r"-\d+-(.+?)-Index", uid)
                            if promotions_match:
                                promotions = promotions_match.group(1)
                                promotions = re.sub(r'^\d+\-', '', promotions)
                                
                            memo_match = re.search(r"Mémo : ([^\n]+)", description)
                            if memo_match:
                                memo = memo_match.group(1)
                        
                        # Convertir les catégories en une chaîne de caractères
                        categories = component.get("CATEGORIES")
                        if categories:
                            categories = ", ".join(categories) if isinstance(categories, list) else str(categories)
                        
                        # Insérer dans la base SQLite avec les nouvelles colonnes
                        cursor.execute("""
                        INSERT OR IGNORE INTO events 
                        (uid, dtstart, dtend, summary, description, location, categories, 
                         matiere, enseignant, promotions, memo)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (uid, dtstart, dtend, summary, description, location, categories,
                              matiere, enseignant, promotions, memo))
                        
                        event_count += 1
                
                print(f"  {event_count} événements importés depuis {ical_file}")
                total_events += event_count
        except Exception as e:
            print(f"Erreur lors de l'importation du fichier {ical_file}: {e}")
    
    # Sauvegarder et fermer
    conn.commit()
    conn.close()
    
    print(f"Base de données créée avec succès. {total_events} événements importés au total.")


files = ["./SQL/M1-ia.txt", "./SQL/M1-ilsen.txt", "./SQL/M1-syrius.txt"]
    
import_calendars(files)


#order the database by dtstart
def order_database():
    """
    Trie la base de données SQLite par date de début (dtstart).
    """
    conn = sqlite3.connect("./SQL/calendar.db")
    cursor = conn.cursor()
    
    # Créer une nouvelle table temporaire pour stocker les événements triés
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sorted_events AS
    SELECT * FROM events ORDER BY dtstart
    """)
    
    # Supprimer l'ancienne table et renommer la nouvelle table
    cursor.execute("DROP TABLE IF EXISTS events")
    cursor.execute("ALTER TABLE sorted_events RENAME TO events")
    
    conn.commit()
    conn.close()
    print("Base de données triée par date de début (dtstart) avec succès.")

order_database()

#remove all the duplicates in the database
def remove_duplicates():
    """
    Supprime les doublons dans la base de données SQLite.
    """
    conn = sqlite3.connect("./SQL/calendar.db")
    cursor = conn.cursor()
    
    # Compter le nombre total d'événements avant suppression
    cursor.execute("SELECT COUNT(*) FROM events")
    count_before = cursor.fetchone()[0]
    
    # Supprimer les doublons (uid) en gardant le premier
    cursor.execute("""
    DELETE FROM events
    WHERE rowid NOT IN (
        SELECT MIN(rowid)
        FROM events
        GROUP BY uid
    )
    """)
    
    # Compter le nombre d'événements après suppression
    cursor.execute("SELECT COUNT(*) FROM events")
    count_after = cursor.fetchone()[0]
    
    # Calculer le nombre de doublons supprimés
    duplicates_removed = count_before - count_after
    
    conn.commit()
    conn.close()
    print(f"Doublons supprimés avec succès. {duplicates_removed} doublons ont été supprimés.")


remove_duplicates()