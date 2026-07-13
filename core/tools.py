import subprocess
import json
import urllib.request
from datetime import datetime
from duckduckgo_search import DDGS

TOOLS = [
    {
        "name": "web_search",
        "description": "Recherche des informations récentes sur le web.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "La requête de recherche"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "run_python",
        "description": "Exécute du code Python et retourne la sortie.",
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Le code Python à exécuter"}
            },
            "required": ["code"]
        }
    },
    {
        "name": "get_weather",
        "description": "Obtient la météo actuelle d'une ville.",
        "input_schema": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "Nom de la ville"}
            },
            "required": ["city"]
        }
    },
    {
        "name": "get_datetime",
        "description": "Retourne la date et l'heure actuelles.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "read_file",
        "description": "Lit le contenu d'un fichier texte local.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Chemin vers le fichier"}
            },
            "required": ["path"]
        }
    },
    {
        "name": "write_file",
        "description": "Crée ou modifie un fichier texte local.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Chemin vers le fichier"},
                "content": {"type": "string", "description": "Contenu à écrire"}
            },
            "required": ["path", "content"]
        }
    },
    {
        "name": "gmail_read",
        "description": "Lit les derniers emails de la boîte Gmail de Sylvanus.",
        "input_schema": {
            "type": "object",
            "properties": {
                "max_emails": {"type": "integer", "description": "Nombre d'emails à lire"},
                "folder": {"type": "string", "description": "Dossier : INBOX, [Gmail]/Sent Messages, etc."},
                "unread_only": {"type": "boolean", "description": "Uniquement les non lus"}
            },
            "required": []
        }
    },
    {
        "name": "gmail_send",
        "description": "Envoie un email depuis le compte Gmail de Sylvanus.",
        "input_schema": {
            "type": "object",
            "properties": {
                "to": {"type": "string", "description": "Adresse email destinataire"},
                "subject": {"type": "string", "description": "Objet de l'email"},
                "body": {"type": "string", "description": "Corps de l'email"}
            },
            "required": ["to", "subject", "body"]
        }
    },
    {
        "name": "gmail_search",
        "description": "Recherche des emails dans la boîte Gmail de Sylvanus.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Mot clé à rechercher"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "calendar_read",
        "description": "Lit les prochains événements du Google Calendar de Sylvanus.",
        "input_schema": {
            "type": "object",
            "properties": {
                "days_ahead": {"type": "integer", "description": "Nombre de jours à venir"}
            },
            "required": []
        }
    },
    {
        "name": "calendar_create",
        "description": "Crée un événement dans le Google Calendar de Sylvanus.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Titre de l'événement"},
                "date": {"type": "string", "description": "Date au format YYYY-MM-DD"},
                "time": {"type": "string", "description": "Heure au format HH:MM"},
                "duration_hours": {"type": "integer", "description": "Durée en heures"},
                "description": {"type": "string", "description": "Description optionnelle"}
            },
            "required": ["title", "date"]
        }
    }
]


def web_search(query: str) -> str:
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=5))
        if not results:
            return "Aucun résultat trouvé."
        lines = [f"**{r['title']}**\n{r['body']}\n{r['href']}" for r in results]
        return "\n\n---\n\n".join(lines)
    except Exception as e:
        return f"Erreur de recherche : {e}"


def run_python(code: str) -> str:
    try:
        result = subprocess.run(
            ["python", "-c", code],
            capture_output=True, text=True, timeout=10
        )
        output = result.stdout or result.stderr
        return output.strip() or "(Aucune sortie)"
    except subprocess.TimeoutExpired:
        return "Timeout : code trop long."
    except Exception as e:
        return f"Erreur : {e}"


def get_weather(city: str) -> str:
    try:
        url = f"https://wttr.in/{city.replace(' ', '+')}?format=j1"
        req = urllib.request.Request(url, headers={"User-Agent": "OrigineS/1.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode())
        c = data["current_condition"][0]
        return (
            f"Météo à {city} :\n"
            f"- {c['weatherDesc'][0]['value']}\n"
            f"- Température : {c['temp_C']}°C (ressenti {c['FeelsLikeC']}°C)\n"
            f"- Humidité : {c['humidity']}%\n"
            f"- Vent : {c['windspeedKmph']} km/h"
        )
    except Exception as e:
        return f"Météo indisponible : {e}"


def get_datetime() -> str:
    now = datetime.now()
    jours = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
    mois = ["janvier", "février", "mars", "avril", "mai", "juin",
            "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
    return f"{jours[now.weekday()]} {now.day} {mois[now.month - 1]} {now.year}, {now.strftime('%H:%M')}"


def read_file(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        if len(content) > 4000:
            return content[:4000] + "\n\n[... tronqué ...]"
        return content
    except FileNotFoundError:
        return f"Fichier introuvable : {path}"
    except Exception as e:
        return f"Erreur lecture : {e}"


def write_file(path: str, content: str) -> str:
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Fichier sauvegardé : {path}"
    except Exception as e:
        return f"Erreur écriture : {e}"


def execute_tool(name: str, tool_input: dict) -> str:
    # Nettoyage du nom si malformé
    if '{' in name:
        name = name.split('{')[0].strip().strip('"')
    if '(' in name:
        name = name.split('(')[0].strip()

    if name in ("gmail_read", "gmail_send", "gmail_search"):
        from core.gmail import gmail_read, gmail_send, gmail_search
        if name == "gmail_read":
            return gmail_read(
                max_emails=tool_input.get("max_emails", 5),
                folder=tool_input.get("folder", "INBOX"),
                unread_only=tool_input.get("unread_only", False)
            )
        elif name == "gmail_send":
            return gmail_send(
                to=tool_input.get("to", ""),
                subject=tool_input.get("subject", ""),
                body=tool_input.get("body", "")
            )
        elif name == "gmail_search":
            return gmail_search(
                query=tool_input.get("query", ""),
                max_emails=tool_input.get("max_emails", 5)
            )

    if name in ("calendar_read", "calendar_create"):
        from core.calendar_tool import calendar_read, calendar_create
        if name == "calendar_read":
            return calendar_read(days_ahead=tool_input.get("days_ahead", 7))
        elif name == "calendar_create":
            return calendar_create(
                title=tool_input.get("title", ""),
                date=tool_input.get("date", ""),
                time=tool_input.get("time", "09:00"),
                duration_hours=tool_input.get("duration_hours", 1),
                description=tool_input.get("description", "")
            )

    dispatch = {
        "web_search": lambda: web_search(tool_input.get("query", "")),
        "run_python": lambda: run_python(tool_input.get("code", "")),
        "get_weather": lambda: get_weather(tool_input.get("city", "Cotonou")),
        "get_datetime": lambda: get_datetime(),
        "read_file": lambda: read_file(tool_input.get("path", "")),
        "write_file": lambda: write_file(tool_input.get("path", ""), tool_input.get("content", "")),
    }
    fn = dispatch.get(name)
    return fn() if fn else f"Outil inconnu : {name}"