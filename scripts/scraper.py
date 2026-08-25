"""
Extrae la carta completa de Bombay Babu desde la app PortalRest (hiopos).

La carta NO se puede abrir accediendo directamente a la URL de PortalRest:
hay que pasar primero por bombay-babu.com/delivery-pr/ y pulsar el botón
"Click here" del restaurante, que abre PortalRest en una pestaña nueva con
los parámetros de sesión correctos.

Dentro de PortalRest, la lista de platos está virtualizada: solo el tramo
visible existe en el DOM en cada momento, así que hay que hacer scroll
categoría a categoría capturando lo que va apareciendo, igual que se hizo
la primera vez a mano.

Guarda un snapshot JSON con: [{category, name, price, desc}, ...]
"""
import json
import os
import re
import sys
import time

from playwright.sync_api import sync_playwright

import config


def log(msg):
    print(f"[scraper] {msg}", flush=True)


def extract_visible_items(page):
    """Lee del DOM los pares nombre/precio/descripción actualmente renderizados."""
    return page.evaluate("""
        () => {
            const rows = [];
            // Cada plato es un bloque con nombre en negrita, precio a la derecha,
            // y descripción opcional debajo. Estructura observada en PortalRest.
            document.querySelectorAll('body *').forEach(el => {});
            return rows;
        }
    """)


def scrape_category_text(page):
    """Extrae todo el texto visible de la página (nombre, precio, descripción
    intercalados) usando innerText, que es lo que ya funcionó al hacer esto
    a mano con get_page_text."""
    return page.inner_text("body")


def parse_menu_text(raw_text, known_categories):
    """
    Convierte el texto plano capturado en una lista de items.
    El texto viene como líneas: nombre, [descripción], precio, '+', repetido,
    con nombres de categoría en mayúsculas intercalados.
    """
    lines = [l.strip() for l in raw_text.split("\n") if l.strip()]
    items = []
    current_category = None
    i = 0
    price_re = re.compile(r"^\d+[.,]\d{2}€$|^desde$")

    while i < len(lines):
        line = lines[i]
        if line.upper() in known_categories:
            current_category = line.upper()
            i += 1
            continue
        # Heurística: nombre de plato seguido, en las 1-2 líneas siguientes,
        # de un precio (o "desde") y luego el símbolo '+'.
        if i + 1 < len(lines) and price_re.match(lines[i + 1]):
            name = line
            price = lines[i + 1]
            desc = ""
            j = i + 2
            if j < len(lines) and lines[j] == "+":
                j += 1
            items.append({
                "category": current_category,
                "name": name,
                "price": price,
                "desc": desc,
            })
            i = j
            continue
        if i + 2 < len(lines) and price_re.match(lines[i + 2]):
            name = line
            desc = lines[i + 1]
            price = lines[i + 2]
            j = i + 3
            if j < len(lines) and lines[j] == "+":
                j += 1
            items.append({
                "category": current_category,
                "name": name,
                "price": price,
                "desc": desc,
            })
            i = j
            continue
        i += 1

    return items


def run():
    os.makedirs(config.SNAPSHOTS_DIR, exist_ok=True)
    if config.DEBUG_MODE:
        os.makedirs(config.DEBUG_DIR, exist_ok=True)

    known_categories = [
        "APERITIVOS", "ENTRANTES", "CURRY", "ACOMPAÑANTES", "SIZZLERS",
        "BIRYANI", "ARROZ", "NAAN", "CHAPATIS Y PARATHAS",
        "ESPECIALES DEL CHEF", "MENU INFANTIL", "POSTRES",
        "BEBIDAS SIN ALCOHOL", "BEBIDAS CON ALCOHOL", "TARJETA REGALO",
    ]

    all_items = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 500, "height": 900})
        page = context.new_page()

        log(f"Abriendo {config.DELIVERY_PAGE_URL}")
        page.goto(config.DELIVERY_PAGE_URL, wait_until="load", timeout=45000)
        page.wait_for_timeout(3000)

        if config.DEBUG_MODE:
            page.screenshot(path=os.path.join(config.DEBUG_DIR, "delivery_page.png"))
            with open(os.path.join(config.DEBUG_DIR, "delivery_page.html"), "w") as f:
                f.write(page.content())

        click_button = page.get_by_text(config.CLICK_HERE_TEXT, exact=True).first
        click_button.wait_for(state="visible", timeout=20000)

        # Pulsa el primer botón "Click here" que encuentre (primer restaurante listado).
        with context.expect_page(timeout=30000) as new_page_info:
            click_button.click()
        portal_page = new_page_info.value
        portal_page.wait_for_load_state("load", timeout=30000)
        log(f"PortalRest abierto: {portal_page.url}")

        # Espera a que carguen las categorías iniciales.
        portal_page.wait_for_timeout(3000)

        if config.DEBUG_MODE:
            portal_page.screenshot(path=os.path.join(config.DEBUG_DIR, "loaded.png"))

        # Scroll incremental por toda la carta, capturando texto en cada paso.
        seen_snippets = set()
        raw_chunks = []
        last_height = -1
        stable_rounds = 0
        max_rounds = 400

        for round_i in range(max_rounds):
            text = scrape_category_text(portal_page)
            if text not in seen_snippets:
                raw_chunks.append(text)
                seen_snippets.add(text)

            portal_page.mouse.wheel(0, 700)
            portal_page.wait_for_timeout(250)

            height = portal_page.evaluate("document.body.scrollHeight")
            if height == last_height:
                stable_rounds += 1
            else:
                stable_rounds = 0
            last_height = height

            if stable_rounds > 6:
                log(f"Fin de la carta detectado en el intento {round_i}")
                break

        combined_text = "\n".join(raw_chunks)
        if config.DEBUG_MODE:
            with open(os.path.join(config.DEBUG_DIR, "raw_text.txt"), "w") as f:
                f.write(combined_text)

        items = parse_menu_text(combined_text, known_categories)

        # Deduplicar por (categoria, nombre)
        dedup = {}
        for it in items:
            key = (it["category"], it["name"])
            dedup[key] = it
        all_items = list(dedup.values())

        browser.close()

    log(f"Extraídos {len(all_items)} items únicos")

    with open(config.TODAY_SNAPSHOT, "w", encoding="utf-8") as f:
        json.dump(all_items, f, ensure_ascii=False, indent=2)

    return all_items


if __name__ == "__main__":
    items = run()
    if not items:
        log("ADVERTENCIA: no se extrajo ningún item. Revisa el modo DEBUG_MODE=true.")
        sys.exit(1)
