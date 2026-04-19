
import os
import sys
from pathlib import Path
from dotenv import load_dotenv, set_key
from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.panel import Panel
from rich.text import Text

console = Console()

def get_config_path():
    """Returns the path to the .env file. 
    Priority: 
    1. Current directory .env (dev mode)
    2. ~/.akari/.env (installed mode)
    """
    local_env = Path.cwd() / ".env"
    if local_env.exists():
        return local_env
    
    akari_home = Path.home() / ".akari"
    akari_home.mkdir(parents=True, exist_ok=True)
    return akari_home / ".env"

def load_config():
    """Loads environment variables from the preferred .env file."""
    config_path = get_config_path()
    if config_path.exists():
        load_dotenv(dotenv_path=config_path, override=True)
        return True
    return False

def save_config_value(key: str, value: str):
    """Saves a single configuration value to the preferred .env file."""
    config_path = get_config_path()
    # Ensure parent directory exists
    config_path.parent.mkdir(parents=True, exist_ok=True)
    # If file doesn't exist, create it
    if not config_path.exists():
        config_path.touch()
    
    set_key(str(config_path), key, value)
    os.environ[key] = value

def ensure_config():
    """Ensures that required configuration (API keys) exists, prompting if necessary (interactive only)."""
    # Load existing config first
    load_config()
    
    # Check if we have what we need in environment variables
    required_keys = ["ANTHROPIC_API_KEY"]
    missing = [k for k in required_keys if not os.getenv(k)]
    
    # If we are in a non-interactive environment (like Docker/Railway), 
    # we don't prompt, we just rely on environment variables.
    is_interactive = sys.stdout.isatty()
    
    if missing and is_interactive:
        console.print(Panel(Text("Welcome to Akari! Let's set up your API keys. 🌸", style="magenta"), border_style="magenta"))
        
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        if not anthropic_key:
            anthropic_key = Prompt.ask("[bold cyan]Enter your Anthropic API Key[/bold cyan]", password=True)
            if not anthropic_key:
                console.print("[red]Anthropic API Key is required to use Akari. Exiting.[/red]")
                sys.exit(1)
            save_config_value("ANTHROPIC_API_KEY", anthropic_key)

        fish_key = os.getenv("FISH_API_KEY")
        if not fish_key:
            if Confirm.ask("[bold cyan]Do you want to enable Voice (Fish Audio)?[/bold cyan]"):
                fish_key = Prompt.ask("[bold cyan]Enter your Fish Audio API Key[/bold cyan]", password=True)
                if fish_key:
                    save_config_value("FISH_API_KEY", fish_key)
                    # Default voice ID
                    save_config_value("FISH_VOICE_ID", "612b878b113047d9a770c069c8b4fdfe")

        user_name = os.getenv("USER_NAME")
        if not user_name:
            user_name = Prompt.ask("[bold cyan]How should I call you? (Username)[/bold cyan]", default="kun")
            save_config_value("USER_NAME", user_name)

        console.print(Panel(Text(f"Setup complete, {os.getenv('USER_NAME')}! Configuration saved ✨", style="magenta"), border_style="magenta"))
    elif missing:
        # On Railway/Docker, we expect environment variables to be set.
        # If they are missing, we should log a warning but not exit immediately 
        # as some parts might work without them (or the user might set them later).
        print(f"WARNING: Missing required environment variables: {', '.join(missing)}")
    else:
        # All good, or at least we have the environment variables.
        pass

if __name__ == "__main__":
    ensure_config()
