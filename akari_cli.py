
import asyncio
import os
import sys
import json
import time
import subprocess
import webbrowser
import httpx
import base64
import tempfile
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict

# Silence all logs
logging.basicConfig(level=logging.CRITICAL)
for logger_name in ["httpx", "anthropic", "akari", "httpcore"]:
    logging.getLogger(logger_name).setLevel(logging.CRITICAL)

import anthropic
from dotenv import load_dotenv
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.live import Live
from rich.spinner import Spinner
from rich.table import Table
from rich.text import Text
from rich.markup import render

# Load environment variables
load_dotenv()

# Import Akari modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from planner import TaskPlanner, detect_planning_mode, PlanningDecision
    from server import extract_action, AKARI_SYSTEM_PROMPT, USER_NAME, PROJECT_DIR, ClaudeTaskManager
    from memory import remember, recall, create_task, get_open_tasks, search_notes
except ImportError:
    pass

console = Console()

# ---------------------------------------------------------------------------
# Config for Voice
# ---------------------------------------------------------------------------
FISH_API_KEY = os.getenv("FISH_API_KEY", "")
FISH_VOICE_ID = os.getenv("FISH_VOICE_ID", "612b878b113047d9a770c069c8b4fdfe")
FISH_API_URL = "https://api.fish.audio/v1/tts"

class AkariCLI:
    def __init__(self):
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            sys.exit(1)
            
        self.client = anthropic.AsyncAnthropic(api_key=self.api_key)
        self.planner = TaskPlanner()
        self.task_manager = ClaudeTaskManager(max_concurrent=3)
        self.conversation_history = []
        self.user_name = os.getenv("USER_NAME", "kun")
        self.project_dir = os.path.dirname(os.path.abspath(__file__))
        self.last_response = ""
        self.session_summary = ""
        self.cached_projects = []
        self.mode = "chat"
        
    def scan_projects(self):
        desktop = Path.home() / "Desktop"
        projects = []
        if desktop.exists():
            try:
                for d in desktop.iterdir():
                    if d.is_dir() and (d / ".git").exists():
                        projects.append({"name": d.name, "path": str(d)})
            except Exception: pass
        self.cached_projects = projects
        return projects

    async def synthesize_speech(self, text: str) -> Optional[bytes]:
        if not FISH_API_KEY: return None
        try:
            async with httpx.AsyncClient(timeout=15.0) as http:
                response = await http.post(FISH_API_URL,
                    headers={"Authorization": f"Bearer {FISH_API_KEY}", "Content-Type": "application/json"},
                    json={"text": text, "reference_id": FISH_VOICE_ID, "format": "mp3"})
                return response.content if response.status_code == 200 else None
        except Exception: return None

    def play_audio(self, audio_bytes: bytes):
        if not audio_bytes: return
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_audio:
            temp_audio.write(audio_bytes)
            temp_path = temp_audio.name
        try:
            cmd = f"powershell -c \"Add-Type -AssemblyName PresentationCore; $player = New-Object System.Windows.Media.MediaPlayer; $player.Open('{temp_path}'); $player.Play(); while($player.NaturalDuration.HasTimeSpan -eq $false){{Start-Sleep -Milliseconds 100}}; Start-Sleep -Milliseconds $player.NaturalDuration.TimeSpan.TotalMilliseconds; $player.Close()\""
            subprocess.run(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        finally:
            if os.path.exists(temp_path):
                try: os.remove(temp_path)
                except: pass

    async def speak(self, text: str):
        audio = await self.synthesize_speech(text)
        if audio:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self.play_audio, audio)

    def print_banner(self):
        banner = r"""
   _____   __  __  ___    ____    ____
  /  _  \ |  |/  ||   \  |    \  |    |
 /  /_\  \|  '  /  |    \ |     \  |  |
/    |    \|    <   |     \|      \ |  |
\____|__  /|__|_ \  |______/|______/|__|
        \/      \/      
        """
        console.print(Panel(Text(banner, style="magenta"), subtitle="[bold magenta]Akari Watanabe — AI Assistant CLI[/bold magenta]", border_style="magenta"))

    async def slow_type(self, text: str, style: str = "magenta", delay: float = 0.03):
        for char in text:
            console.print(Text(char, style=style), end="")
            await asyncio.sleep(delay)

    async def handle_api_limit(self):
        limit_msg = "Darling, it looks like you're out of API... 🌸"
        limit_audio_path = Path(self.project_dir) / "data" / "audio" / "[Akari Watanabe] API Limit.mp3"
        if limit_audio_path.exists():
            try:
                audio_bytes = limit_audio_path.read_bytes()
                asyncio.get_event_loop().run_in_executor(None, self.play_audio, audio_bytes)
            except Exception: pass
        await self.slow_type(limit_msg, style="bold magenta", delay=0.05)
        console.print()

    async def type_welcome_message(self):
        welcome_msg = (
            f"おかえriなさい、あなた! ✨\n\n"
            "Welcome to the AKARI CLI. I'm so happy to see you working hard today! "
            "Together, we can build amazing things. 🌸\n\n"
            "Type /help to see what I can do!"
        )
        typed_text = ""
        with Live(Panel(Text("", style="magenta"), border_style="magenta"), refresh_per_second=20) as live:
            for char in welcome_msg:
                typed_text += char
                # Highlight /help in the message
                highlighted = Text(typed_text, style="magenta")
                if "/help" in typed_text:
                    highlighted.highlight_regex(r"/help", "bold cyan")
                live.update(Panel(highlighted, border_style="magenta"))
                await asyncio.sleep(0.01)

    async def get_system_prompt(self):
        now = datetime.now()
        current_time = now.strftime("%A, %B %d, %Y at %I:%M %p")
        projects_str = "\n".join([f"- {p['name']} ({p['path']})" for p in self.cached_projects])
        system = AKARI_SYSTEM_PROMPT.format(
            current_time=current_time, weather_info="Dynamic CLI", screen_context="CLI",
            calendar_context="Active", mail_context="Active", active_tasks=self.task_manager.get_active_tasks_summary(),
            dispatch_context="", known_projects=projects_str, user_name=self.user_name, project_dir=self.project_dir,
        )
        return system

    async def execute_action(self, action: Dict):
        action_type, target = action["action"], action["target"]
        console.print(f"\n[bold yellow]Action:[/bold yellow] [cyan]{action_type.upper()}[/cyan] -> {target}")
        if action_type == "browse":
            url = target if target.startswith("http") else f"https://www.google.com/search?q={target}"
            webbrowser.open(url)
            return f"Opened browser."
        elif action_type in ["build", "research"]:
            path = Path.home() / "Desktop" / f"akari_{target.replace(' ', '_')[:20]}"
            os.makedirs(path, exist_ok=True)
            cmd = f"start cmd /k \"cd /d {path} && claude -p\"" if sys.platform == "win32" else f'tell application "Terminal" to do script "cd {path} && claude -p"'
            subprocess.Popen(cmd, shell=True) if sys.platform == "win32" else subprocess.run(["osascript", "-e", cmd])
            return f"Started task in {path}."
        elif action_type == "add_task":
            create_task(target); return "Task added."
        elif action_type == "remember":
            remember(target); return "Memory saved."
        return f"Action {action_type} triggered."

    async def handle_command(self, cmd: str):
        cmd = cmd.lower().strip()
        if cmd == "/help":
            # 1. Play Help Audio
            help_audio_path = Path(self.project_dir) / "data" / "audio" / "[Akari Watanabe] Help.mp3"
            if help_audio_path.exists():
                try:
                    asyncio.get_event_loop().run_in_executor(None, self.play_audio, help_audio_path.read_bytes())
                except Exception: pass
            
            # 2. Type the message
            console.print(f"[bold magenta]Akari:[/bold magenta] ", end="")
            await self.slow_type("What help do you need, darling? ✨", style="bold magenta", delay=0.03)
            console.print("\n")
            
            # 3. Show Table
            table = Table(title="Akari CLI Commands", border_style="magenta")
            table.add_column("Command", style="cyan")
            table.add_column("Description", style="white")
            table.add_row("/help", "Show this help message")
            table.add_row("/clear", "Clear screen and reset conversation context")
            table.add_row("/tasks", "List all open tasks")
            table.add_row("/projects", "List scanned projects on Desktop")
            table.add_row("/restart", "Restart the server (simulated in CLI)")
            table.add_row("/quit", "Sayonara and exit")
            console.print(table)
        elif cmd == "/clear":
            # 1. Play Clean Audio
            clean_audio_path = Path(self.project_dir) / "data" / "audio" / "[Akari Watanabe] Clean.mp3"
            if clean_audio_path.exists():
                try:
                    asyncio.get_event_loop().run_in_executor(None, self.play_audio, clean_audio_path.read_bytes())
                except Exception: pass
            
            # 2. Show Response
            console.print(f"[bold magenta]Akari:[/bold magenta] ", end="")
            await self.slow_type("I've cleaned it, darling. ✨", style="bold magenta", delay=0.03)
            await asyncio.sleep(1)

            # 3. Clear and Reset
            self.conversation_history = []
            console.clear()
            self.print_banner()
            console.print("[dim]Context reset. Screen cleared.[/dim]")
        elif cmd == "/projects":
            self.scan_projects()
            if not self.cached_projects: console.print("[dim]No projects found on Desktop.[/dim]")
            else:
                for p in self.cached_projects: console.print(f"📁 [bold cyan]{p['name']}[/bold cyan] [dim]({p['path']})[/dim]")
        elif cmd == "/tasks":
            tasks = get_open_tasks()
            if not tasks: console.print("[dim]No open tasks! You're all caught up, darling. ✨[/dim]")
            else:
                for t in tasks: console.print(f"✅ [green]{t['title']}[/green] [dim](ID: {t['id']})[/dim]")
        elif cmd == "/restart":
            # 1. Play Restart Audio
            restart_audio_path = Path(self.project_dir) / "data" / "audio" / "[Akari Watanabe] Restart.mp3"
            if restart_audio_path.exists():
                try:
                    asyncio.get_event_loop().run_in_executor(None, self.play_audio, restart_audio_path.read_bytes())
                except Exception: pass
            
            # 2. Show Response
            console.print(f"[bold magenta]Akari:[/bold magenta] ", end="")
            await self.slow_type("Restarting systems, darling... 🌸", style="bold magenta", delay=0.03)
            await asyncio.sleep(2)
            
            # 3. Simulate Restart (In CLI we just re-run main_loop or exit and let a shell script handle it, 
            # but here we'll just re-initialize conversation)
            self.conversation_history = []
            console.clear()
            self.print_banner()
            await self.type_welcome_message()
        return True

    async def chat(self, user_input: str):
        try:
            if self.mode == "planning":
                result = await self.planner.process_answer(user_input, self.cached_projects)
                if result["plan_complete"]:
                    self.mode = "chat"
                    plan = self.planner.active_plan
                    await self.speak("Executing plan!")
                    console.print(f"\n[bold magenta]Akari:[/bold magenta] ", end="")
                    await self.slow_type("Plan finalized. Executing now... 🚀\n", style="bold green")
                    if plan: await self.execute_action({"action": plan.task_type, "target": plan.original_request})
                    return None
                else:
                    q = result['next_question']
                    await self.speak(q)
                    console.print(f"\n[bold magenta]Akari:[/bold magenta] ", end="")
                    await self.slow_type(q); return None

            decision = await detect_planning_mode(user_input, self.client)
            if decision.needs_planning:
                self.mode = "planning"
                result = await self.planner.start_planning(user_input, self.cached_projects)
                if result["needs_questions"]:
                    q = result['first_question']; await self.speak(q)
                    console.print(f"\n[bold magenta]Akari:[/bold magenta] ", end="")
                    await self.slow_type(q); return None
                else:
                    self.mode = "chat"; await self.speak("On it!")
                    console.print(f"\n[bold magenta]Akari:[/bold magenta] ", end="")
                    await self.slow_type("Task understood. Executing... 🚀\n", style="bold green")
                    await self.execute_action({"action": decision.task_type, "target": user_input})
                    return None
                
            system_prompt = await self.get_system_prompt()
            messages = self.conversation_history + [{"role": "user", "content": user_input}]
            full_response = ""
            console.print(f"\n[bold magenta]Akari:[/bold magenta] ", end="")
            async with self.client.messages.stream(model="claude-3-5-sonnet-20241022", max_tokens=1024, system=system_prompt, messages=messages) as stream:
                async for text in stream.text_stream:
                    for char in text:
                        console.print(Text(char, style="magenta"), end=""); await asyncio.sleep(0.01)
                    full_response += text
            console.print() 
            clean_text, action = extract_action(full_response)
            asyncio.create_task(self.speak(clean_text))
            if action:
                action_result = await self.execute_action(action)
                console.print(f"[dim italic]{action_result}[/dim italic]")
            self.conversation_history.append({"role": "user", "content": user_input})
            self.conversation_history.append({"role": "assistant", "content": full_response})
            return None
        except Exception as e:
            if any(x in str(e).lower() for x in ["400", "credit", "billing", "balance"]):
                await self.handle_api_limit()
            return None

    async def main_loop(self):
        self.scan_projects()
        self.print_banner()
        welcome_file_path = Path(self.project_dir) / "data" / "audio" / "[Akari Watanabe] Welcome Message.mp3"
        if welcome_file_path.exists():
            try:
                welcome_audio = welcome_file_path.read_bytes()
                asyncio.get_event_loop().run_in_executor(None, self.play_audio, welcome_audio)
            except Exception: pass
        else: asyncio.create_task(self.speak(f"Okaerinasai, {self.user_name}!"))
        await self.type_welcome_message()

        while True:
            try:
                user_input = Prompt.ask(f"\n[bold cyan]{self.user_name}[/bold cyan]" if self.mode == "chat" else f"\n[bold yellow]{self.mode.upper()}[/bold yellow]")
                if not user_input.strip(): continue
                
                if user_input.startswith("/"):
                    if user_input.lower() in ["/quit", "/exit", "sayonara"]:
                        bye_text = "Sayonara darin... 🌸"
                        goodbye_file_path = Path(self.project_dir) / "data" / "audio" / "[Akari Watanabe] Goodbye Message.mp3"
                        if goodbye_file_path.exists():
                            asyncio.get_event_loop().run_in_executor(None, self.play_audio, goodbye_file_path.read_bytes())
                        console.print("\n", end="")
                        await self.slow_type(bye_text, style="bold magenta", delay=0.1)
                        console.print("\n"); await asyncio.sleep(1.5); return 
                    await self.handle_command(user_input)
                    continue

                await self.chat(user_input)
            except KeyboardInterrupt: break
            except Exception: pass

if __name__ == "__main__":
    cli = AkariCLI()
    asyncio.run(cli.main_loop())
