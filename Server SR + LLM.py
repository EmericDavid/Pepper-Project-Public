#!/usr/bin/env python
# -*- coding: utf-8 -*-

import base64
import wave
import speech_recognition as sr
from flask import Flask, request, jsonify
from ast import literal_eval
import os
import sqlite3
from google import genai
from google.genai import types
import SQL.test_calendar_llm_V6 as calendar
import pandas as pd

from datetime import datetime
#date = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
#put the date at monday 5 may 2025 17h
date = "05/05/2025 17:24:16"

from dotenv import load_dotenv
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
os.environ["GEMINI_API_KEY"] = api_key

# Historique de conversation pour l'assistant Pepper
# Note: Gemini n'accepte pas le rôle "system", on utilise "user" à la place
conversation_history = [
    {"role": "user", "content": f"""
Nous sommes le {date}.
Tu es Pepper, un robot assistant. Tes reponses doivent etre donc courtes et simples. Tes reponses ne doivent pas execeder 1 phrase.


Si l'utilisateur demande un dab, repond avec le code : "Do_dab"
Si l'utilisateur demande explicitement d'arreter repond avec le code: "No_more_speech"
Si l'utilisateur a une question sur le calendrier, repond avec le code: "Calendar_question"
"""}
]

app = Flask(__name__)

def speechRecognition(data, params):
    r = sr.Recognizer()
    audioFileName = 'temp_audio.wav'

    # Convertir les données et les paramètres de base64 et les décoder
    data = base64.b64decode(data)
    params = base64.b64decode(params)
    params = literal_eval(params.decode("utf-8"))

    # Écrire les données audio dans un fichier temporaire
    with wave.open(audioFileName, "wb") as wave_write:
        wave_write.setparams(params)
        wave_write.writeframes(data)

    # Transcrire le fichier audio
    with sr.AudioFile(audioFileName) as source:
        audio = r.record(source)
    try:
        result_transcribe = r.recognize_google(audio, language="fr-FR")
        print("Transcription :", result_transcribe)
        return result_transcribe
    except sr.UnknownValueError:
        print("Impossible de transcrire l'audio")
        return None
    except sr.RequestError as e:
        return f"Je crois qu'il y a une erreur dans le service de reconnaissance vocale; {e}"

def chat_completion(new_message: str) -> str:
    # Initialiser le client Gemini
    client = genai.Client(
        api_key=os.environ.get("GEMINI_API_KEY"),
    )
    
    # Append the new message to conversation history with 'user' role
    conversation_history.append({"role": "user", "content": new_message})
    
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
    
    print("User voice capté:", new_message)
    print("LLM:", model_message)
    return model_message


def chat_completion_from_sql(new_message: str) -> str:
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

Les informations interessantes sont les suivantes :
- Nom du cours (pas l'identifiant)
- Enseignant
- Date de début
- Date de fin
- Salle
- Type de cours (CM, TD, TP, etc.)
- Le memo si accocié à l'événement est interessant
Voici la reponse SQL de notre base de données : {new_message}
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
    
    print("User voice capté:", new_message)
    print("LLM:", model_message)
    return model_message

@app.route("/google", methods=["POST"])
def transcribe():
    req_data = request.get_json(force=True)
    user_text = speechRecognition(req_data['data'], req_data['params'])
    action_text = "No_action"
    #si speechRecognition retourne une exception UnknownValueError renvoie une chaine vide
    if user_text == None:
        return jsonify({"sentence": "No_speech", "action": "No_action"})

    response_text = chat_completion(user_text)

    if "Calendar_question" in response_text:
        assistant_calendar = calendar.CalendarAssistant()

        response_text, action_text = assistant_calendar.ask_assistant_calendar(user_text.lower())

    #si response_text contient "No_more_speech"
    if "No_more_speech" in response_text:
        response_text = "Au revoir !"
        action_text = "No_more_speech"
        
    #si response_text contient "Do_dab"
    if "Do_dab" in response_text:
        response_text = "Voici mon dab !"
        action_text = "Do_dab"

    print(f"\033[92mSentence: \033[0m{response_text}")
    print(f"\033[91mAction: \033[0m{action_text}")
    
    return jsonify({"sentence": response_text, "action": action_text})

if __name__ == "__main__":
    app.run(host='0.0.0.0', debug=False)