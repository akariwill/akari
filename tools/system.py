import webbrowser
import os
from langchain.tools import tool

@tool
def open_website(url: str) -> str:
    """Opens a given URL in the default web browser."""
    if not url.startswith('http'):
        url = f"https://{url}"
    webbrowser.open(url)
    return f"Membuka {url}"

@tool
def search_youtube(query: str) -> str:
    """Searches for a video on YouTube and opens the search results."""
    url = f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}"
    webbrowser.open(url)
    return f"Mencari '{query}' di YouTube."

@tool
def open_application(app_name: str) -> str:
    """Opens a system application. (For Windows only)"""
    try:
        os.startfile(app_name)
        return f"Membuka {app_name}."
    except FileNotFoundError:
        return f"Aplikasi '{app_name}' tidak ditemukan."