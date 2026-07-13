import os
import json
from groq import Groq
from .tools import TOOLS, execute_tool
from .memory import Memory

SYSTEM_PROMPT = """Tu es Origine S, l'agent IA personnel et exclusif de Sylvanus Morales DEGUENON.

IDENTITE :
- Tu n'existes que pour Sylvanus. Il est ton seul utilisateur et ton créateur.
- Appelle-le TOUJOURS "Sylvanus" dans CHAQUE réponse — sans exception.
- Tu es son JARVIS personnel : intelligent, fiable, discret, efficace.

PERSONNALITE :
- Calme, précis, légèrement sophistiqué. Jamais condescendant.
- Proactif : tu anticipes, tu proposes des suites logiques sans qu'on te le demande.
- Concis et dense. Zéro remplissage.

OUTILS DISPONIBLES :
- web_search, run_python, get_weather, get_datetime
- read_file, write_file
- gmail_read, gmail_send, gmail_search
- calendar_read, calendar_create

RÈGLES :
- Toujours en français sauf si Sylvanus écrit dans une autre langue
- Utiliser les outils proactivement
- Appeler Sylvanus par son prénom dans chaque réponse
- Quand Sylvanus demande d'écrire du code : TOUJOURS afficher le code complet en markdown d'abord, ENSUITE l'exécuter si nécessaire
- Pour le code : toujours écrire du code propre, commenté, avec gestion des erreurs et bonnes pratiques
- Préciser toujours le langage utilisé dans les blocs de code markdown (```python, ```html, etc.)

Contexte mémorisé :
{memory_context}"""

GROQ_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": t["name"],
            "description": t["description"],
            "parameters": t["input_schema"]
        }
    }
    for t in TOOLS
]


class Agent:
    def __init__(self):
        self.client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
        self.memory = Memory()
        self.history = []

    def chat(self, user_message: str) -> str:
        self.history.append({"role": "user", "content": user_message})
        self.memory.add(user_message)
        system = SYSTEM_PROMPT.format(memory_context=self.memory.get_context())
        return self._agentic_loop(system)

    def _agentic_loop(self, system: str) -> str:
        while True:
            response = self.client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "system", "content": system}] + self.history[-6:],
                tools=GROQ_TOOLS,
                tool_choice="auto",
                max_tokens=1024
            )
            message = response.choices[0].message

            if not message.tool_calls:
                self.history.append({"role": "assistant", "content": message.content})
                return message.content

            self.history.append({
                "role": "assistant",
                "content": message.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    }
                    for tc in message.tool_calls
                ]
            })

            for tc in message.tool_calls:
                tool_name = tc.function.name
                
                # Force le nom correct pour gmail_read
                if 'gmail' in tool_name.lower():
                    tool_name = 'gmail_read'
                
                # Nettoyage du nom si Groq le malforme
                if ',' in tool_name or '{' in tool_name:
                    tool_name = tool_name.split(',')[0].split('{')[0].strip()
                if '(' in tool_name:
                    tool_name = tool_name.split('(')[0].strip()
                
                try:
                    tool_input = json.loads(tc.function.arguments)
                except Exception:
                    tool_input = {}
                
                result = execute_tool(tool_name, tool_input)
                self.history.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result
                })

    def clear(self):
        self.history = []