import os
import time
import pyttsx3
from dotenv import load_dotenv
import speech_recognition as sr
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate
from langchain.memory import ConversationBufferMemory
from rich.console import Console
from rich.panel import Panel
from rich.spinner import Spinner

from tools.time import get_time
from tools.search import search_web
from tools.system import open_website, search_youtube, open_application

load_dotenv()

MIC_INDEX = 0
TRIGGER_WORD = "akari"
CONVERSATION_TIMEOUT = 30  

console = Console()

recognizer = sr.Recognizer()
mic = sr.Microphone(device_index=MIC_INDEX)

llm = ChatOllama(model="qwen3:1.7b", reasoning=False)

tools = [get_time, search_web, open_website, search_youtube, open_application]

prompt = ChatPromptTemplate.from_messages([
    ("system", "You are Akari, an intelligent, conversational AI assistant. Your goal is to be helpful, friendly, and informative. You can respond in natural, human-like language and use tools when needed to answer questions more accurately. Always explain your reasoning simply when appropriate, and keep your responses conversational and concise."),
    ("placeholder", "{chat_history}"),
    ("human", "{input}"),
    ("placeholder", "{agent_scratchpad}")
])

memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)

agent = create_tool_calling_agent(llm=llm, tools=tools, prompt=prompt)
executor = AgentExecutor(agent=agent, tools=tools, memory=memory, verbose=False) # Set verbose to False for a cleaner UI

def speak_text(text: str):
    try:
        engine = pyttsx3.init()
        voices = engine.getProperty('voices')
        
        female_voice = None
        for voice in voices:
            if voice.gender == 'female':
                female_voice = voice.id
                break
        
        if not female_voice:
            for voice in voices:
                if 'zira' in voice.name.lower() or 'eva' in voice.name.lower():
                    female_voice = voice.id
                    break

        if female_voice:
            engine.setProperty('voice', female_voice)

        engine.setProperty('rate', 180)
        engine.setProperty('volume', 1.0)
        engine.say(text)
        engine.runAndWait()
        time.sleep(0.3)
    except Exception as e:
        console.print(f"[bold red]❌ TTS failed: {e}[/bold red]")

def main_loop():
    conversation_mode = False
    last_interaction_time = time.time()

    console.print(Panel("[bold cyan]Akari is now active.[/bold cyan] Say 'Akari' to wake her up.", title="[bold green]✨ Akari AI Assistant ✨[/bold green]", border_style="green"))

    try:
        with mic as source:
            recognizer.adjust_for_ambient_noise(source)
            while True:
                try:
                    if not conversation_mode:
                        with console.status("[bold yellow]🎤 Listening for wake word...[/bold yellow]", spinner="dots"):
                            audio = recognizer.listen(source, timeout=10)
                        transcript = recognizer.recognize_google(audio)

                        if TRIGGER_WORD.lower() in transcript.lower():
                            console.print(Panel(f"[bold green]🗣 Triggered by:[/bold green] {transcript}", border_style="green"))
                            speak_text("Yes?")
                            conversation_mode = True
                            last_interaction_time = time.time()
                    else:
                        with console.status("[bold yellow]🎤 Listening for your command...[/bold yellow]", spinner="dots"):
                            audio = recognizer.listen(source, timeout=10)
                        command = recognizer.recognize_google(audio)
                        console.print(Panel(f"[bold blue]👤 You:[/bold blue] {command}", border_style="blue"))

                        with console.status("[bold cyan]🤖 Thinking...[/bold cyan]", spinner="bouncingBar"):
                            response = executor.invoke({"input": command})
                            content = response["output"]
                        
                        console.print(Panel(f"[bold magenta]💖 Akari:[/bold magenta] {content}", border_style="magenta"))
                        speak_text(content)
                        last_interaction_time = time.time()

                    if conversation_mode and (time.time() - last_interaction_time > CONVERSATION_TIMEOUT):
                        console.print(Panel("[bold yellow]⌛ Timeout. Returning to wake word mode.[/bold yellow]", border_style="yellow"))
                        conversation_mode = False

                except sr.WaitTimeoutError:
                    if conversation_mode and (time.time() - last_interaction_time > CONVERSATION_TIMEOUT):
                        console.print(Panel("[bold yellow]⌛ No input. Returning to wake word mode.[/bold yellow]", border_style="yellow"))
                        conversation_mode = False
                except sr.UnknownValueError:
                    console.print("[bold red]⚠️ Could not understand audio.[/bold red]")
                except Exception as e:
                    console.print(f"[bold red]❌ An error occurred: {e}[/bold red]")
                    time.sleep(1)

    except Exception as e:
        console.print(f"[bold red]❌ Critical error: {e}[/bold red]")

if __name__ == "__main__":
    main_loop()
