import os
import sys
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

from core.agent import Agent
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.text import Text
from rich.table import Table
from rich import box

console = Console()
voice_mode = False
stt = None
tts = None


def print_banner():
    console.print(Panel.fit(
        Text.assemble(
            ("ORIGINE S\n", "bold white"),
            ("Agent IA Personnel — Phase 3\n", "dim"),
            ("web | Python | Memoire | Voix\n", "dim"),
            ("Tape /help pour les commandes", "dim")
        ),
        border_style="white"
    ))


def print_help():
    table = Table(box=box.SIMPLE, show_header=True, header_style="bold white")
    table.add_column("Commande", style="green")
    table.add_column("Description", style="dim")
    table.add_row("/help", "Afficher cette aide")
    table.add_row("/history", "Voir la conversation en cours")
    table.add_row("/save", "Sauvegarder la conversation")
    table.add_row("/memory", "Voir la memoire long terme")
    table.add_row("/tools", "Voir les outils disponibles")
    table.add_row("/voice", "Activer/desactiver le mode vocal")
    table.add_row("/clear", "Effacer la conversation")
    table.add_row("/exit", "Quitter Origine S")
    console.print(table)


def print_tools():
    table = Table(box=box.SIMPLE, show_header=True, header_style="bold white")
    table.add_column("Outil", style="green")
    table.add_column("Description", style="dim")
    table.add_row("web_search", "Recherche sur le web en temps reel")
    table.add_row("run_python", "Execute du code Python")
    console.print(table)


def print_history(history: list):
    if not history:
        console.print("[dim]Aucun historique.[/dim]")
        return
    for msg in history:
        if msg["role"] == "user" and isinstance(msg["content"], str):
            console.print(f"[green]Vous :[/green] {msg['content']}")
        elif msg["role"] == "assistant" and isinstance(msg["content"], str):
            console.print(f"[white]Origine S :[/white] {msg['content'][:200]}...")
        console.print("")


def save_conversation(history: list):
    if not history:
        console.print("[dim]Rien a sauvegarder.[/dim]")
        return
    filename = f"conversation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    lines = []
    for msg in history:
        if msg["role"] == "user" and isinstance(msg["content"], str):
            lines.append(f"[{datetime.now().strftime('%H:%M')}] Vous : {msg['content']}")
        elif msg["role"] == "assistant" and isinstance(msg["content"], str):
            lines.append(f"[{datetime.now().strftime('%H:%M')}] Origine S : {msg['content']}")
        lines.append("")
    with open(filename, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    console.print(f"[green]Conversation sauvegardee dans {filename}[/green]")


def toggle_voice():
    global voice_mode, stt, tts
    if not voice_mode:
        try:
            from voice.stt import STT
            from voice.tts import TTS
            if stt is None:
                console.print("[dim]Chargement du modele vocal...[/dim]")
                stt = STT()
                tts = TTS()
            voice_mode = True
            console.print("[green]Mode vocal active. Parle apres le signal.[/green]")
        except Exception as e:
            console.print(f"[red]Erreur activation voix : {e}[/red]")
    else:
        voice_mode = False
        console.print("[yellow]Mode vocal desactive.[/yellow]")


def voice_loop(agent: Agent):
    console.print(f"\n[dim]{datetime.now().strftime('%H:%M')}[/dim] [bold yellow]Ecoute... (5 secondes)[/bold yellow]")
    try:
        audio = stt.record()
        with console.status("[dim]Transcription...[/dim]"):
            user_input = stt.transcribe(audio)
        if not user_input:
            console.print("[dim]Rien entendu.[/dim]")
            return
        console.print(f"[green]Vous (voix) :[/green] {user_input}")
        with console.status("[bold white]Origine S reflechit...[/bold white]"):
            response = agent.chat(user_input)
        timestamp = datetime.now().strftime("%H:%M")
        console.print(f"\n[dim]{timestamp}[/dim] [bold white]Origine S[/bold white]")
        console.print(Markdown(response))
        tts.speak(response)
    except Exception as e:
        console.print(f"[red]Erreur voix : {e}[/red]")


def main():
    if not os.environ.get("GROQ_API_KEY"):
        console.print("[red]GROQ_API_KEY manquante dans .env[/red]")
        sys.exit(1)

    print_banner()
    agent = Agent()

    while True:
        try:
            if voice_mode:
                voice_loop(agent)
                continue
            user_input = Prompt.ask(
                f"\n[dim]{datetime.now().strftime('%H:%M')}[/dim] [bold green]Vous[/bold green]"
            )
        except (KeyboardInterrupt, EOFError):
            console.print("\n[yellow]Origine S hors ligne.[/yellow]")
            break

        user_input = user_input.strip()
        if not user_input:
            continue

        if user_input.lower() == "/exit":
            console.print("[yellow]Origine S hors ligne. A bientot.[/yellow]")
            break
        elif user_input.lower() == "/help":
            print_help()
            continue
        elif user_input.lower() == "/tools":
            print_tools()
            continue
        elif user_input.lower() == "/history":
            print_history(agent.history)
            continue
        elif user_input.lower() == "/save":
            save_conversation(agent.history)
            continue
        elif user_input.lower() == "/memory":
            console.print(f"\n[dim]{agent.memory.get_context()}[/dim]")
            continue
        elif user_input.lower() == "/voice":
            toggle_voice()
            continue
        elif user_input.lower() == "/clear":
            agent.clear()
            console.print("[yellow]Conversation effacee.[/yellow]")
            continue

        with console.status("[bold white]Origine S reflechit...[/bold white]"):
            try:
                response = agent.chat(user_input)
            except Exception as e:
                console.print(f"[red]Erreur : {e}[/red]")
                continue

        timestamp = datetime.now().strftime("%H:%M")
        console.print(f"\n[dim]{timestamp}[/dim] [bold white]Origine S[/bold white]")
        console.print(Markdown(response))


if __name__ == "__main__":
    main()