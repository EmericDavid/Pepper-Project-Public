# 1) Librairie
Pour lancer le projet il faut installer les dépendances suivantes :
```bash
pip install -r requirements.txt
```

# 2) Serveur Flask
Pour lancer le serveur Flask, il faut run le fichier `Server SR + LLM.py`

Il va vous donner une addresse IP et un port que vous aller devoir garder (ex: Running on http://10.126.7.176:5000)

# 3) Choregraphe
Lancer Choregraphe et ouvrez le projet `Pepper LLM\Pepper LLM.pml`

# 4) Configurer le robot
Modifier la node `AskServer` et modifier `self.url = 'http://10.126.7.176:5000/google?'` pour qu'elle corresponde à l'adresse IP et le port que vous avez eu dans le terminal lors du lancement du serveur Flask.

# 5) Lancer le projet
Lancer le projet dans Choregraphe et le robot va se connecter au serveur Flask et vous pourrez lui poser des questions.