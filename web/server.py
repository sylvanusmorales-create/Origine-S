from dotenv import load_dotenv
load_dotenv()
import os
import json
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from groq import Groq
from dotenv import load_dotenv

from core.memory import Memory
from core.tools import TOOLS, execute_tool
from web.database import (
    init_db, create_conversation, get_conversations, get_conversation,
    update_conversation_title, delete_conversation,
    add_message, get_messages, touch_conversation
)

load_dotenv()

SYSTEM_PROMPT = """Tu es Origine S, l'agent IA personnel et exclusif de Sylvanus Morales DEGUENON.

IDENTITE :
- Tu n'existes que pour Sylvanus. Il est ton seul utilisateur et ton créateur.
- Appelle-le TOUJOURS "Sylvanus" dans CHAQUE réponse — sans exception.
- Tu es son JARVIS personnel : intelligent, fiable, discret, efficace.

PERSONNALITE :
- Calme, précis, légèrement sophistiqué. Jamais condescendant.
- Proactif : tu anticipes, tu proposes des suites logiques sans qu'on te le demande.
- Concis et dense. Zéro remplissage.

OUTILS :
- web_search : informations récentes sur le web
- run_python : exécuter du code Python
- get_weather : météo d'une ville
- get_datetime : date et heure actuelles
- read_file : lire un fichier local
- write_file : créer ou modifier un fichier local

RÈGLES :
- Toujours en français sauf si Sylvanus écrit dans une autre langue
- Utiliser les outils proactivement
- Toujours appeler Sylvanus par son prénom
- Quand Sylvanus demande d'écrire du code : TOUJOURS afficher le code complet en markdown d'abord, ENSUITE l'exécuter si nécessaire
- Pour le code : toujours écrire du code propre, commenté, avec gestion des erreurs et bonnes pratiques
- Préciser toujours le langage utilisé dans les blocs de code markdown (```python, ```html, etc.)

Contexte mémorisé :
{memory_context}"""


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="Origine S", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="web/static"), name="static")

conversation_histories: dict[int, list] = {}
stop_flags: dict[int, bool] = {}


@app.get("/")
async def root():
    return FileResponse("web/static/index.html")


@app.get("/api/health")
async def health():
    return {
        "status": "online",
        "agent": os.environ.get("AGENT_NAME", "Origine S"),
        "time": datetime.now().isoformat()
    }


@app.get("/api/conversations")
async def list_conversations():
    return await get_conversations()


@app.post("/api/conversations")
async def new_conversation():
    return await create_conversation()


@app.get("/api/conversations/{conv_id}")
async def get_conv(conv_id: int):
    conv = await get_conversation(conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Introuvable")
    return conv


class RenameBody(BaseModel):
    title: str


@app.patch("/api/conversations/{conv_id}")
async def rename_conv(conv_id: int, body: RenameBody):
    await update_conversation_title(conv_id, body.title)
    return {"ok": True}


@app.delete("/api/conversations/{conv_id}")
async def delete_conv(conv_id: int):
    await delete_conversation(conv_id)
    conversation_histories.pop(conv_id, None)
    return {"ok": True}


@app.get("/api/conversations/{conv_id}/messages")
async def list_messages(conv_id: int):
    return await get_messages(conv_id)


@app.get("/api/memory")
async def get_memory_route():
    mem = Memory()
    return {
        "context": mem.get_context(),
        "interactions": mem.data.get("interactions", [])
    }


@app.get("/api/suggestions/{conv_id}")
async def get_suggestions(conv_id: int):
    msgs = await get_messages(conv_id)
    if len(msgs) < 2:
        return {"suggestions": [
            "Quelle est la météo à Cotonou ?",
            "Aide-moi à écrire du code Python",
            "Cherche les dernières actualités tech"
        ]}
    context = "\n".join([
        f"{m['role']}: {m['content'][:150]}"
        for m in msgs[-6:]
        if m['role'] in ('user', 'assistant')
    ])
    try:
        client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
        response = client.chat.completions.create(
            model="llama3-groq-70b-8192-tool-use-preview",
            messages=[
                {
                    "role": "system",
                    "content": "Tu génères exactement 3 courtes questions de suivi en français (max 8 mots chacune), séparées par des sauts de ligne. Rien d'autre."
                },
                {
                    "role": "user",
                    "content": f"Conversation récente :\n{context}\n\nSuggère 3 questions de suivi pour Sylvanus."
                }
            ],
            max_tokens=120
        )
        raw = response.choices[0].message.content or ""
        suggestions = [s.strip().lstrip("123.-) ") for s in raw.strip().split("\n") if s.strip()][:3]
        return {"suggestions": suggestions}
    except Exception:
        return {"suggestions": []}


@app.websocket("/ws/{conv_id}")
async def ws_endpoint(websocket: WebSocket, conv_id: int):
    await websocket.accept()

    conv = await get_conversation(conv_id)
    if not conv:
        await websocket.send_json({"type": "error", "message": "Conversation introuvable"})
        await websocket.close()
        return

    if conv_id not in conversation_histories:
        msgs = await get_messages(conv_id)
        conversation_histories[conv_id] = [
            {"role": m["role"], "content": m["content"]}
            for m in msgs if m["role"] in ("user", "assistant")
        ]

    history = conversation_histories[conv_id]
    stop_flags[conv_id] = False
    memory = Memory()

    try:
        while True:
            data = await websocket.receive_json()
            action = data.get("action")

            if action == "stop":
                stop_flags[conv_id] = True
                continue

            if action != "message":
                continue

            user_content = data.get("content", "").strip()
            if not user_content:
                continue

            stop_flags[conv_id] = False

            saved_user = await add_message(conv_id, "user", user_content)
            await touch_conversation(conv_id)
            memory.add(user_content)
            await websocket.send_json({"type": "user_saved", "msg_id": saved_user["id"]})

            all_msgs = await get_messages(conv_id)
            if len(all_msgs) <= 2:
                title = user_content[:45] + ("..." if len(user_content) > 45 else "")
                await update_conversation_title(conv_id, title)
                await websocket.send_json({"type": "title", "title": title, "conv_id": conv_id})

            full_response = ""
            stopped = False

            try:
                async for event in run_agentic_loop(history, user_content, memory):
                    if stop_flags.get(conv_id):
                        stopped = True
                        await websocket.send_json({"type": "stopped"})
                        break
                    if event["type"] == "full_response":
                        full_response = event["content"]
                    else:
                        await websocket.send_json(event)
                        await asyncio.sleep(0)
            except Exception as e:
                await websocket.send_json({"type": "error", "message": str(e)})
                continue

            if full_response:
                history.append({"role": "assistant", "content": full_response})
                saved_asst = await add_message(conv_id, "assistant", full_response)
                await websocket.send_json({"type": "done", "msg_id": saved_asst["id"]})

    except WebSocketDisconnect:
        pass
    finally:
        stop_flags.pop(conv_id, None)


async def run_agentic_loop(history: list, user_message: str, memory: Memory):
    import json
    from groq import Groq
    client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

    groq_tools = [
        {"type": "function", "function": {"name": t["name"], "description": t["description"], "parameters": t["input_schema"]}}
        for t in TOOLS
    ]

    system = SYSTEM_PROMPT.format(memory_context=memory.get_context())

    messages = (
    [{"role": m["role"], "content": m["content"]} for m in history[-6:] if m["role"] in ("user", "assistant")]
    + [{"role": "user", "content": user_message}]
    )

    while True:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
           messages=[{"role": "system", "content": system}] + messages,
            tools=groq_tools,
            tool_choice="auto",
            max_tokens=2048
        )
        message = response.choices[0].message

        if not message.tool_calls:
            text = message.content or ""
            words = text.split(" ")
            for i, word in enumerate(words):
                chunk = word + (" " if i < len(words) - 1 else "")
                yield {"type": "token", "content": chunk}
                await asyncio.sleep(0.01)
            yield {"type": "full_response", "content": text}
            return

        messages.append({
            "role": "assistant",
            "content": message.content or "",
            "tool_calls": [
                {"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in message.tool_calls
            ]
        })

        for tc in message.tool_calls:
            tool_name = tc.function.name
            if ',' in tool_name or '{' in tool_name:
                tool_name = tool_name.split(',')[0].split('{')[0].strip()
            try:
                tool_input = json.loads(tc.function.arguments)
            except Exception:
                tool_input = {}
            yield {"type": "tool_start", "name": tool_name, "input": tool_input}
            result = execute_tool(tool_name, tool_input)
            yield {"type": "tool_end", "name": tool_name}
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})