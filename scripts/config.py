"""
Configuración central del monitor de la carta de Bombay Babu.
"""
import os

# URL de la web de Bombay Babu con el flujo de acceso a la carta digital.
# Cambia la ruta si el restaurante de referencia cambia.
DELIVERY_PAGE_URL = "https://bombay-babu.com/delivery-pr/"

# Texto del botón que abre la carta digital (PortalRest) en la página de delivery.
CLICK_HERE_TEXT = "Click here"

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SNAPSHOTS_DIR = os.path.join(REPO_ROOT, "scripts", "snapshots")
TODAY_SNAPSHOT = os.path.join(SNAPSHOTS_DIR, "latest.json")
PREVIOUS_SNAPSHOT = os.path.join(SNAPSHOTS_DIR, "previous.json")

INDEX_HTML_PATH = os.path.join(REPO_ROOT, "index.html")

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = "claude-sonnet-4-6"

DEBUG_MODE = os.environ.get("DEBUG_MODE", "false").lower() == "true"
DEBUG_DIR = os.path.join(REPO_ROOT, "scripts", "debug")
