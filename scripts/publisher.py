"""
Llama a la API de Claude con el snapshot actual de la carta y el resumen de
cambios detectados, y le pide que devuelva el bloque JS `CATEGORIES` de
index.html actualizado — sin tocar el resto del documento (CSS, hero, lógica
de render), igual que se acordó para el sistema de El Capricho.
"""
import json
import re

import anthropic

import config


SYSTEM_PROMPT = """Eres el encargado de mantener actualizado el array JavaScript
`CATEGORIES` dentro de la página HTML de la carta digital de Bombay Babu
(restaurantes tandoori, Tenerife).

Reglas:
- Recibes el array CATEGORIES actual (JS) y una lista de items actualizados
  extraídos hoy de la carta real (con categoría, nombre, precio y descripción).
- Debes devolver ÚNICAMENTE el nuevo array CATEGORIES completo en JS válido,
  sin explicación, sin markdown, sin ```js — empieza directamente por
  "const CATEGORIES = [" y termina en "];".
- Mantén exactamente la misma estructura de objetos ya usada: id, tag, title,
  sub, items (arrays [nombre, precio, descripción]), y priceGroup/note cuando
  ya existan en la categoría correspondiente (curry -> priceGroup:'curry',
  biryani -> priceGroup:'biryani', sizzlers -> note existente).
- Conserva el id, tag, title y sub de cada categoría tal cual estaban, solo
  actualiza/añade/elimina items según lo que indique la lista de hoy.
- Si un plato de hoy no trae descripción, deja la cadena vacía ''.
- Si el precio es "desde", pon el string 'desde' igual que en el original
  (el desglose por proteína se muestra aparte, no lo toques).
- No inventes platos ni descripciones que no estén en los datos de hoy.
- No cambies el orden de las categorías.
"""


def build_user_message(current_categories_js, items_today, diff_summary):
    items_json = json.dumps(items_today, ensure_ascii=False, indent=2)
    return f"""ARRAY CATEGORIES ACTUAL:
{current_categories_js}

ITEMS EXTRAÍDOS HOY (fuente de verdad):
{items_json}

RESUMEN DE CAMBIOS DETECTADOS RESPECTO A AYER:
{diff_summary or '(sin cambios detectados por el differ, pero regenera igualmente por consistencia)'}

Devuelve el array CATEGORIES completo actualizado."""


def extract_categories_block(html):
    match = re.search(r"const CATEGORIES = \[.*?\n\];", html, re.DOTALL)
    if not match:
        raise ValueError("No se encontró el bloque CATEGORIES en index.html")
    return match.group(0), match.start(), match.end()


def regenerate(items_today, diff_summary):
    with open(config.INDEX_HTML_PATH, encoding="utf-8") as f:
        html = f.read()

    current_block, start, end = extract_categories_block(html)

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    response = client.messages.create(
        model=config.ANTHROPIC_MODEL,
        max_tokens=8000,
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": build_user_message(current_block, items_today, diff_summary),
        }],
    )

    new_block = response.content[0].text.strip()
    if not new_block.startswith("const CATEGORIES"):
        raise ValueError("La respuesta de Claude no empieza por 'const CATEGORIES' — abortando por seguridad.")

    new_html = html[:start] + new_block + html[end:]

    with open(config.INDEX_HTML_PATH, "w", encoding="utf-8") as f:
        f.write(new_html)

    return True
