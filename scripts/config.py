"""
Configuración central del monitor de la carta de Bombay Babu.
"""
import os

# Enlace directo a PortalRest que aterriza en la carta con solo 2 clics en
# la misma pestaña (¿Para cuándo? -> Ahora; ¿Cómo? -> A recoger en local).
# Más simple y fiable que pasar por bombay-babu.com/delivery-pr/, que requiere
# abrir una pestaña nueva y falla en modo headless.
PORTALREST_DIRECT_URL = "https://www.portalrest.com/index.html?data=wETPsNGcmATPrNXYmITPtZCO1YTOwMTP0NXZSRWa"

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SNAPSHOTS_DIR = os.path.join(REPO_ROOT, "scripts", "snapshots")
TODAY_SNAPSHOT = os.path.join(SNAPSHOTS_DIR, "latest.json")
PREVIOUS_SNAPSHOT = os.path.join(SNAPSHOTS_DIR, "previous.json")

INDEX_HTML_PATH = os.path.join(REPO_ROOT, "index.html")

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = "claude-sonnet-4-6"

DEBUG_MODE = os.environ.get("DEBUG_MODE", "false").lower() == "true"
DEBUG_DIR = os.path.join(REPO_ROOT, "scripts", "debug")

