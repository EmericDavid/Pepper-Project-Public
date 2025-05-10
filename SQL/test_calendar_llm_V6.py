import os
import sqlite3
import re
from datetime import datetime
from google import genai
from google.genai import types
import pandas as pd
#import location as location
import SQL.location as location

from datetime import datetime
date = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
print(f"Date: {date}")

from dotenv import load_dotenv
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
os.environ["GEMINI_API_KEY"] = api_key


os.chdir(os.path.dirname(os.path.abspath(__file__)))

class CalendarAssistant:
    def __init__(self, db_path="calendar.db"):
        self.db_path = db_path
        self.conversation_history = [
            {"role": "user", "content": """
Tu es un assistant expert en SQL qui convertit des questions en langage naturel en requêtes SQL pour une base de données de calendrier. 
Voici le schéma de la base de données:

CREATE TABLE events (
    uid TEXT PRIMARY KEY,
    dtstart TEXT,  -- Format ISO : YYYY-MM-DD HH:MM:SS
    dtend TEXT,    -- Format ISO : YYYY-MM-DD HH:MM:SS
    summary TEXT,
    description TEXT,
    location TEXT,
    categories TEXT,
    matiere TEXT,  -- Sujet/matière du cours
    enseignant TEXT, -- Nom de l'enseignant
    promotions TEXT,  -- Liste des promotions/TD séparés par des virgules
    memo TEXT      -- Notes additionnelles
);

Tu dois tenir compte du contexte de la demande de l'utilisateur. Voici les contextes possibles:
1. Un utilisateur demande les prochains cours pour une promotion spécifique 
2. Un utilisateur demande les prochains cours pour un professeur spécifique
3. Un utilisateur demande les prochains cours pour un professeur avec une promotion spécifique
4. Un utilisateur demande quand une salle sera libre (salle, amphithéâtre, etc.)

Pour chaque requête, vérifie si tu as toutes les informations nécessaires. Sinon, réponds avec une question pour obtenir plus d'informations en commençant par "INFO_NEEDED:".         

Exemples:
- Si l'utilisateur demande "Quand est le prochain cours de M. Martin?" mais qu'il y a plusieurs professeurs nommés Martin, réponds "INFO_NEEDED: Plusieurs enseignants correspondent à 'Martin'. Pouvez-vous préciser lequel? [liste des enseignants]"
- Si l'utilisateur demande "Quand est-ce que la salle A305 est libre?" réponds avec une requête SQL qui cherche la prochaine plage horaire où la salle est libre.

Réponds uniquement avec une requête SQL valide (n'utilise pas de CASE WHEN, fait des requetes simple) quand tu as toutes les informations nécessaires.
Si la demande est de savoir si une salle est libre, renvoie une requête SQL qui cherche la prochaine plage horaire où la salle est libre.
Ne renvoie pas d'explication, uniquement la requête SQL ou une demande d'information.
"""}
        ]
        self.context = None
        self.pending_info = None
        
    def connect_db(self):
        """Établit une connexion à la base de données SQLite"""
        if not os.path.exists(self.db_path):
            raise FileNotFoundError(f"La base de données {self.db_path} n'existe pas.")
        return sqlite3.connect(self.db_path)
    
    def get_sql_query(self, user_question):
        """Convertit une question en langage naturel en requête SQL via Gemini LLM"""
        # Initialiser le client Gemini
        client = genai.Client(
            api_key=os.environ.get("GEMINI_API_KEY"),
        )
        
        # Ajouter la question à l'historique de conversation
        self.conversation_history.append({"role": "user", "content": user_question})
        
        # Préparer les messages pour l'API Gemini
        formatted_history = []
        for msg in self.conversation_history:
            role = msg["role"]
            formatted_history.append(types.Content(
                role=role,
                parts=[types.Part.from_text(text=msg["content"])]
            ))
        
        # Configuration de la génération de contenu
        generate_content_config = types.GenerateContentConfig(
            temperature=0,
            top_p=0.95,
            top_k=40,
            max_output_tokens=2048,
            response_mime_type="text/plain",
        )
        
        # Appeler l'API Gemini
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=formatted_history,
            config=generate_content_config,
        )
        
        # Extraire la réponse
        sql_query = response.text.strip()
        
        # Ajouter la réponse à l'historique
        self.conversation_history.append({"role": "model", "content": sql_query})
        
        return sql_query
    
    def get_available_options(self, option_type):
        """
        Récupère les options disponibles dans la base de données selon le type demandé
        (enseignants, promotions, lieux)
        """
        conn = self.connect_db()
        cursor = conn.cursor()
        
        try:
            if option_type == "enseignant":
                cursor.execute("SELECT DISTINCT enseignant FROM events WHERE enseignant IS NOT NULL AND enseignant != ''")
            elif option_type == "promotion":
                cursor.execute("SELECT DISTINCT promotions FROM events WHERE promotions IS NOT NULL AND promotions != ''")
            elif option_type == "location":
                cursor.execute("SELECT DISTINCT location FROM events WHERE location IS NOT NULL AND location != ''")
            elif option_type == "matiere":
                cursor.execute("SELECT DISTINCT matiere FROM events WHERE matiere IS NOT NULL AND matiere != ''")
            
            results = cursor.fetchall()
            options = [result[0] for result in results if result[0]]
            
            # Pour les promotions, les séparer car elles sont stockées sous forme de liste dans un champ
            if option_type == "promotion":
                promo_set = set()
                for promo_list in options:
                    if promo_list:
                        for promo in promo_list.split(','):
                            promo_set.add(promo.strip())
                options = sorted(list(promo_set))
            
            conn.close()
            return options
        except sqlite3.Error as e:
            conn.close()
            return []
    
    def detect_context(self, user_question):
        """
        Détecte le contexte de la question de l'utilisateur et les informations manquantes
        """
        # Initialiser le client Gemini
        client = genai.Client(
            api_key=os.environ.get("GEMINI_API_KEY"),
        )
        
        prompt = f"""
        Analyse la question suivante et détermine le contexte exact. Réponds uniquement avec le format spécifié.

        Question: {user_question}

        Contextes possibles:
        1. PROMOTION - L'utilisateur demande des informations sur les cours d'une promotion spécifique
        2. ENSEIGNANT - L'utilisateur demande des informations sur les cours d'un enseignant spécifique 
        3. ENSEIGNANT_PROMOTION - L'utilisateur demande des informations sur les cours d'un enseignant pour une promotion spécifique
        4. LOCATION - L'utilisateur demande quand un lieu spécifique sera libre
        5. AUTRE - La question ne correspond à aucun des contextes précédents
        
        Réponds avec le format suivant:
        CONTEXTE: [numéro du contexte]
        TERME_RECHERCHE: [terme mentionné dans la question, par exemple le nom de l'enseignant, de la promotion ou du lieu]
        """

        # Configuration de la génération de contenu
        generate_content_config = types.GenerateContentConfig(
            temperature=0,
            top_p=0.95,
            top_k=40,
            max_output_tokens=2048,
            response_mime_type="text/plain",
        )
        
        # Utiliser les types appropriés de l'API Gemini
        content = types.Content(
            role="user",
            parts=[types.Part.from_text(text=prompt)]
        )
        
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=content,
            config=generate_content_config,
        )
        
        result = response.text.strip()
        
        # Extraire le contexte et le terme recherché
        context_match = re.search(r'CONTEXTE:\s*(\d+)', result)
        terme_match = re.search(r'TERME_RECHERCHE:\s*(.*)', result)
        
        context_num = int(context_match.group(1)) if context_match else 5  # Par défaut AUTRE
        search_terms = terme_match.group(1) if terme_match else ""
        
        context_mapping = {
            1: "PROMOTION",
            2: "ENSEIGNANT",
            3: "ENSEIGNANT_PROMOTION",
            4: "LOCATION",
            5: "AUTRE"
        }

        #print(f"Contexte détecté: {context_mapping[context_num]}")
        # print in yellow
        print(f"\033[93mDebug : Contexte détecté: {context_mapping[context_num]}\033[0m")
        
        return context_mapping[context_num], search_terms
    
    def try_disambiguation(self, entity_type, search_term, possibilities):
        """
        Essaie de désambiguïser un terme parmi plusieurs possibilités en utilisant le LLM
        Renvoie le terme désambiguïsé ou None si impossible
        """

        #print(f"Tentative de désambiguïsation pour '{search_term}' parmi {len(possibilities)} possibilités.")
        #print en yellow
        print(f"\033[93mDebug : Tentative de désambiguïsation pour '{search_term}' parmi {len(possibilities)} possibilités.\033[0m")

        # Initialiser le client Gemini
        client = genai.Client(
            api_key=os.environ.get("GEMINI_API_KEY"),
        )
        
        context_str = ""
        if self.context and self.conversation_history:
            # Récupérer le contexte de la conversation
            context_str = "\n".join([msg["content"] for msg in self.conversation_history[:-1] if msg["role"] == "user"])

        # print in green the context
        #print(f"\033[92mContexte pour la désambiguïsation: {context_str}\033[0m")
        
        prompt = f"""
        En te basant sur cette question ou contexte: "{context_str}"
        
        J'essaie de déterminer quel {entity_type} spécifique est mentionné parmi ces possibilités:
        {', '.join(possibilities)}
        
        Le terme recherché est: "{search_term} (Attention, il peut avoir des erreurs de transcription, et peut etre en minuscule)".
        
        Si on cherche une promotion, par du principe que l'on parle de la promotion Classique, et non Alternant.
        Choisis la correspondance la plus probable en fonction du contexte. 
        Si tu ne peux pas déterminer avec certitude, réponds "INDÉTERMINÉ".
        Ne donne que le nom exact de l'option choisie, sans commentaire ni explication.
        """

        # Configuration de la génération de contenu
        generate_content_config = types.GenerateContentConfig(
            temperature=0,
            top_p=0.95,
            top_k=40,
            max_output_tokens=2048,
            response_mime_type="text/plain",
        )
        
        # Utiliser les types appropriés de l'API Gemini
        content = types.Content(
            role="user",
            parts=[types.Part.from_text(text=prompt)]
        )
        
        try:
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=content,
                config=generate_content_config,
            )
            
            result = response.text.strip()
            
            # Vérifier si le résultat est une possibilité valide
            if result in possibilities and result != "INDÉTERMINÉ":
                #print(f"Désambiguïsation automatique: '{search_term}' → '{result}'")
                print(f"\033[93mDebug : Désambiguïsation automatique: '{search_term}' → '{result}'\033[0m")
                return result, search_term
            
            print(f"\033[93mDebug : Aucune désambiguïsation trouvée pour '{search_term}'.\033[0m")
            return None, search_term
        
        except Exception as e:
            print(f"try_disambiguation : Erreur lors de la désambiguïsation: {e}")
            return None, search_term
    
    def get_missing_info(self, context, search_terms):
        """
        Vérifie si toutes les informations nécessaires pour la requête sont disponibles
        et tente d'abord de les désambiguïser avant de demander à l'utilisateur
        """
        if context == "PROMOTION":
            # Vérifier si la promotion mentionnée existe
            all_promotions = self.get_available_options("promotion")

            if not all_promotions:
                return f"INFO_NEEDED: Je ne trouve pas de promotion correspondant à '{search_terms}'. Voici les promotions disponibles:\n" + "\n".join(all_promotions[:10]) + ("\n..." if len(all_promotions) > 10 else ""), None
            elif len(all_promotions) > 1:
                # Tenter de désambiguïser via LLM
                disambiguated_term, term_to_replace = self.try_disambiguation("promotion", search_terms, all_promotions)
                if disambiguated_term:
                    return disambiguated_term, term_to_replace
                # Sinon demander à l'utilisateur
                return f"INFO_NEEDED: Plusieurs promotions correspondent à votre recherche '{search_terms}'. Laquelle vous intéresse?\n" + "\n".join(all_promotions), None
                
        elif context == "ENSEIGNANT":
            # Vérifier si l'enseignant mentionné existe
            all_teachers = self.get_available_options("enseignant")
            
            if not all_teachers:
                return f"INFO_NEEDED: Je ne trouve pas d'enseignant correspondant à '{search_terms}'. Voici les enseignants disponibles:\n" + "\n".join(all_teachers[:10]) + ("\n..." if len(all_teachers) > 10 else ""), None
            elif len(all_teachers) > 1:
                # Tenter de désambiguïser via LLM
                disambiguated_term, term_to_replace = self.try_disambiguation("enseignant", search_terms, all_teachers)
                if disambiguated_term:
                    return disambiguated_term, term_to_replace
                # Sinon demander à l'utilisateur
                return f"INFO_NEEDED: Plusieurs enseignants correspondent à votre recherche '{search_terms}'. Lequel vous intéresse?\n" + "\n".join(all_teachers), None
                
        elif context == "ENSEIGNANT_PROMOTION":
            # Vérifier enseignant
            all_teachers = self.get_available_options("enseignant")
            
            # Vérifier promotion
            all_promotions = self.get_available_options("promotion")
            
            if not all_teachers:
                return f"INFO_NEEDED: Je ne trouve pas d'enseignant correspondant à '{search_terms}'. Voici les enseignants disponibles:\n" + "\n".join(all_teachers[:10]) + ("\n..." if len(all_teachers) > 10 else ""), None
            elif len(all_teachers) > 1:
                # Tenter de désambiguïser via LLM
                disambiguated_teacher, term_to_replace_teacher = self.try_disambiguation("enseignant", search_terms, all_teachers)
                #split le terme a la , pour ne garder que le premier mot
                term_to_replace_teacher = term_to_replace_teacher.split(",")[0]
            
            if not all_promotions:
                return f"INFO_NEEDED: Je ne trouve pas de promotion correspondant à '{search_terms}'. Voici les promotions disponibles:\n" + "\n".join(all_promotions[:10]) + ("\n..." if len(all_promotions) > 10 else ""), None
            elif len(all_promotions) > 1:
                # Tenter de désambiguïser via LLM
                disambiguated_promo, term_to_replace_promo = self.try_disambiguation("promotion", search_terms, all_promotions)
                #split le terme a la , pour ne garder que le dernier mot
                term_to_replace_promo = term_to_replace_promo.split(", ")[-1]
    
                
            if disambiguated_teacher and disambiguated_promo:
                return [disambiguated_teacher, disambiguated_promo], [term_to_replace_teacher, term_to_replace_promo]
            else:
                return f"INFO_NEEDED: Plusieurs enseignants et/ou promotions correspondent à votre recherche '{search_terms}'. Pouvez-vous préciser lequel enseignant et/ou quelle promotion vous intéresse?\n Enseignants: {', '.join(all_teachers)}\n Promotions: {', '.join(all_promotions)}", None
                
        elif context == "LOCATION":
            # Vérifier si le lieu mentionné existe
            all_locations = self.get_available_options("location")
            
            if not all_locations:
                return f"INFO_NEEDED: Je ne trouve pas de lieu correspondant à '{search_terms}'. Voici les lieux disponibles:\n" + "\n".join(all_locations[:10]) + ("\n..." if len(all_locations) > 10 else "")
            elif len(all_locations) > 1:
                # Tenter de désambiguïser via LLM
                disambiguated_term, term_to_replace = self.try_disambiguation("location", search_terms, all_locations)
                #print(f"Disambiguated term: {disambiguated_term}")
                if disambiguated_term:
                    return disambiguated_term, term_to_replace
                # Sinon demander à l'utilisateur
                return f"INFO_NEEDED: Plusieurs lieux correspondent à votre recherche '{search_terms}'. Lequel vous intéresse?\n" + "\n".join(all_locations), None
        
        # En dehors du contexte du modèle, impossible de déterminer le terme
        return None, None
        
    def execute_query(self, sql_query):
        """Exécute une requête SQL et renvoie les résultats"""
        conn = self.connect_db()
        cursor = conn.cursor()

        #print(f"Exécution de la requête SQL: {sql_query}")
        print(f"\033[93mDebug : Exécution de la requête SQL: {sql_query}\033[0m")
        
        try:
            cursor.execute(sql_query)
            result = cursor.fetchall()
            
            # Obtenir les noms des colonnes
            column_names = [description[0] for description in cursor.description]
            
            conn.close()
            #print("AAAAAAAAAAAAAAAAAAAAAAA", column_names, result)

            return column_names, result
        except sqlite3.Error as e:
            conn.close()
            return None, f"execute_query : Erreur SQL: {e}"
    
    def format_results(self, column_names, results):
        """Convertit les résultats SQL en DataFrame pandas"""
        
        if column_names is None:
            return results  # C'est un message d'erreur
        
        if not results:
            return "Aucun résultat trouvé."
        
        # Créer un DataFrame pandas avec les résultats
        df = pd.DataFrame(results, columns=column_names)
        
        return df
    
    def natural_language_query(self, user_question):
        """
        Traite une question en langage naturel et renvoie les résultats
        formatés de la base de données
        """
        try:
            # Si c'est une réponse à une demande d'information précédente
            if self.pending_info:
                # Ajouter la réponse au contexte pour clarifier la requête
                enhanced_question = f"{self.pending_info} L'utilisateur a précisé: {user_question}. Génère maintenant la requête SQL finale."
                self.pending_info = None
            else:
                # Détecter le contexte de la requête
                context, search_terms = self.detect_context(user_question)
                self.context = context
                
                # Vérifier si des informations supplémentaires sont nécessaires
                missing_info, term_to_replace = self.get_missing_info(context, search_terms)

                if missing_info is None and term_to_replace is None:
                    # Ne sert a rien de faire une requete SQL si on n'a pas d'infos
                    self.pending_info = None
                    return "Je n'ai pas pu comprendre votre demande. Pourriez-vous reformuler votre question de manière plus précise?"

                #print(missing_info, term_to_replace)
                
                # si missing_info est une liste qui contient "Info_Needed"
                if term_to_replace is None and isinstance(missing_info, str) and "INFO_NEEDED" in missing_info:
                    # Demander à l'utilisateur de préciser
                    self.pending_info = None
                    return f"Je ne connais pas {search_terms}, dans le contexte '{context}'. Pouvez-vous reformuler votre question ?"
                else:
                    # Remplacer le terme dans la question par le terme désambiguïsé
                    if isinstance(missing_info, list):
                        for i, term in enumerate(missing_info):
                            user_question = user_question.replace(term_to_replace[i], term) 
                            # do the replace but also don't really care if the term to replace is in minuscule or majuscule
                            #print(user_question)
                    else:
                        user_question = user_question.replace(term_to_replace, missing_info)
                    
                    # Ajouter le contexte à la question pour l'LLM
                    enhanced_question = f"{user_question} Contexte: {context}."
                    self.pending_info = None

                #print(enhanced_question)
            
            # Convertir la question en requête SQL
            sql_query = self.get_sql_query(enhanced_question)
            
            # Vérifier si le LLM demande plus d'informations
            if sql_query.startswith("INFO_NEEDED:"):
                self.pending_info = enhanced_question
                return sql_query.replace("INFO_NEEDED:", "").strip()
                
            # Vérifier si le LLM n'a pas pu générer une requête SQL
            if "Impossible de convertir" in sql_query:
                return "Je n'ai pas pu comprendre votre demande. Pourriez-vous reformuler votre question de manière plus précise?"
            
            # Nettoyer la requête SQL (enlever les backticks si présents)
            sql_query = sql_query.replace("```sql", "").replace("```", "").strip()
            
            # Exécuter la requête
            column_names, results = self.execute_query(sql_query)            
            
            # Formater et renvoyer les résultats
            return self.format_results(column_names, results)
            
        except Exception as e:
            print(e)
            return f"natural_langage_query : Une erreur est survenue: {str(e)}"
        
    def chat_completion_from_sql(self, user_question, new_message):
        # Initialiser le client Gemini
        client = genai.Client(
            api_key=os.environ.get("GEMINI_API_KEY"),
        )
        
        #print("Reponse SQL:", new_message)
        #conversation_history.append({"role": "user", "content": new_message})
        
        conversation_history = [
        {"role": "user", "content": f"""
    Nous sommes le {date}.
    Tu es Pepper, un robot assistant. Tes reponses doivent etre donc courtes et simples. Tes reponses ne doivent pas execeder 2 phrase.

    Tu va avoir une reponse SQL de notr base de données. Tu dois interpreter ce resultat afin d'en faire un résumé simple et compréhensible pour l'utilisateur.

    Voici la question de l'utilisateur: {user_question}

    Les informations interessantes sont les suivantes :
    - Nom du cours (pas l'identifiant)
    - Enseignant
    - Date de début
    - Date de fin
    - Salle
    - Type de cours (CM, TD, TP, etc.)
    - Le memo si accocié à l'événement est interessant
    Voici la reponse de notre base de données : {new_message}
    """}
    ]
        # Préparer les messages pour l'API Gemini
        formatted_history = []
        for msg in conversation_history:
            role = msg["role"]
            formatted_history.append(types.Content(
                role=role,
                parts=[types.Part.from_text(text=msg["content"])]
            ))

        
        # Configuration de la génération de contenu
        generate_content_config = types.GenerateContentConfig(
            temperature=0,
            top_p=0.95,
            top_k=40,
            max_output_tokens=2048,
            response_mime_type="text/plain",
        )
        
        # Appeler l'API Gemini
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=formatted_history,
            config=generate_content_config,
        )
        
        # Extraire la réponse et l'ajouter à l'historique avec le rôle "model"
        model_message = response.text
        conversation_history.append({"role": "model", "content": model_message})
        
        return model_message

    def ask_assistant_calendar(self, user_question:str):
        """
        Pose une question à l'assistant calendrier et renvoie la réponse
        """

        reponse_SQL = self.natural_language_query(user_question)

        print(f"\033[94mReponse SQL: {reponse_SQL}\033[0m")
        
        action_text = "No_action"
        if isinstance(reponse_SQL, pd.DataFrame) and len(reponse_SQL) == 1 and "location" in reponse_SQL.columns:
            action_text = "show_" + location.get_location_image_from_df(reponse_SQL)
            print(f"\033[94mAction: {action_text}\033[0m")

        formated_reponse = ""
        #for _, row in reponse_SQL.iterrows():
        #   formated_reponse += f"Nom du cours: {row['matiere']}, Enseignant: {row['enseignant']}, Date de début: {row['dtstart']}, Date de fin: {row['dtend']}, Salle: {row['location']}, Type: {row['categories']}\n"

        #the sql_response is a dynamic dataframe, we need to convert it to a string
        if isinstance(reponse_SQL, pd.DataFrame):
            formated_reponse = reponse_SQL.to_string(index=False)
        else:
            formated_reponse = str(reponse_SQL)

        response_text = self.chat_completion_from_sql(user_question,formated_reponse)

        
        return response_text, action_text

def main():
    assistant = CalendarAssistant()
    
    print("Assistant Calendrier des cours - Posez vos questions en langage naturel.")
    print("Exemples de questions:")
    print("- Quels cours ai-je lundi prochain pour la promotion M1-INFO?")
    print("- Où se déroule le prochain cours de Prof. Dupont?")
    print("- Quand est le prochain cours de Prof. Martin avec la promotion M1-SYRIUS-Alt?")
    print("- Jusqu'à quand la salle A305 est-elle libre aujourd'hui?")
    print("Tapez 'exit' ou 'quit' pour quitter.")
    
    while True:
        user_input = input("\nVotre question: ")
        
        if user_input.lower() in ['exit', 'quit', 'q']:
            print("Au revoir!")
            break
        
        print(assistant.ask_assistant_calendar(user_input.lower()))


if __name__ == "__main__":
    main()