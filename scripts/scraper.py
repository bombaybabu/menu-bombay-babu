"""
Extrae la carta completa de Bombay Babu desde la app PortalRest (hiopos).

Se accede mediante un enlace directo de portalrest.com que, con solo 2 clics
en la MISMA pestaña, aterriza en la carta — sin necesidad de pasar por
bombay-babu.com/delivery-pr/ ni de abrir una pestaña nueva:
  1. https://www.portalrest.com/index.html?data=... (URL fija, ver config.py)
  2. Pantalla "¿Para cuándo?" → clic en "Ahora"
  3. Pantalla "¿Cómo?" → clic en "A recoger en local"
  4. Aterriza en la carta (shop-letter/<id1>/<id2>)

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

from playwright.sync_api import sync_playwright

import config


def log(msg):
    print(f"[scraper] {msg}", flush=True)


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
        context = browser.new_context(
            viewport={"width": 500, "height": 900},
            locale="es-ES",
            timezone_id="Atlantic/Canary",
            extra_http_headers={"Accept-Language": "es-ES,es;q=0.9"},
        )
        page = context.new_page()

        log(f"Abriendo {config.PORTALREST_DIRECT_URL}")
        page.goto(config.PORTALREST_DIRECT_URL, wait_until="load", timeout=60000)
        page.wait_for_timeout(3000)

        if config.DEBUG_MODE:
            page.screenshot(path=os.path.join(config.DEBUG_DIR, "step1_when.png"))
            with open(os.path.join(config.DEBUG_DIR, "step1_when.html"), "w") as f:
                f.write(page.content())

        # Banner de cookies (si aparece): aceptar para no bloquear los clics siguientes.
        # Se intenta por selector, y si no desaparece, por coordenadas de píxel
        # directas (el botón "Aceptar" siempre aparece en la misma zona del
        # viewport 500x900).
        cookie_re = re.compile(r"Ok|Aceptar|Accept", re.IGNORECASE)
        try:
            page.get_by_role("button", name=cookie_re).first.click(timeout=5000, force=True)
        except Exception:
            try:
                page.get_by_text(cookie_re).first.click(timeout=3000, force=True)
            except Exception:
                pass
        for attempt in range(4):
            try:
                page.get_by_text("cookies", exact=False).first.wait_for(state="hidden", timeout=1500)
                break
            except Exception:
                if config.DEBUG_MODE:
                    page.screenshot(path=os.path.join(config.DEBUG_DIR, f"cookie_attempt_{attempt}.png"))
                page.keyboard.press("Escape")
                try:
                    page.locator(".cdk-overlay-backdrop").first.click(timeout=1000, force=True)
                except Exception:
                    pass
                # Clic directo por coordenadas sobre el botón "Aceptar" (zona
                # inferior del viewport 500x900), como último recurso.
                try:
                    page.mouse.click(251, 861)
                except Exception:
                    pass
                page.wait_for_timeout(500)
        page.wait_for_timeout(1000)

        if config.DEBUG_MODE:
            page.screenshot(path=os.path.join(config.DEBUG_DIR, "step1c_after_cookies.png"))

        # Pantalla "¿Para cuándo?" / "For when?": si el restaurante está abierto
        # aparece "Ahora"/"Now"; si está cerrado, solo aparece la opción de
        # seleccionar día y hora manualmente. El idioma puede variar (es/en)
        # según cómo la app decida el idioma, así que se aceptan ambos.
        ahora_re = re.compile(r"\bAhora\b|\bNow\b", re.IGNORECASE)
        seleccionar_re = re.compile(r"Seleccionar día y hora|Select day and hour", re.IGNORECASE)
        ahora_btn = page.get_by_text(ahora_re).first
        try:
            ahora_btn.wait_for(state="visible", timeout=15000)
            ahora_btn.click(force=True)
        except Exception:
            log("Restaurante cerrado: seleccionando día/hora manualmente")
            page.get_by_text(seleccionar_re).first.click(timeout=15000, force=True)
            page.wait_for_timeout(1500)
            if config.DEBUG_MODE:
                page.screenshot(path=os.path.join(config.DEBUG_DIR, "step1b_datetime.png"))
            # Primero hay que elegir un día en el calendario (celda no
            # deshabilitada de Angular Material), y solo entonces aparece
            # la lista de horas disponibles para ese día.
            try:
                page.locator(".mat-calendar-body-cell:not(.mat-calendar-body-disabled)").first.click(
                    timeout=8000, force=True
                )
            except Exception:
                # Alternativa: cualquier botón/celda de día que no esté claramente deshabilitado.
                page.locator("[class*='calendar'][class*='cell']:not([aria-disabled='true'])").first.click(
                    timeout=5000, force=True
                )
            page.wait_for_timeout(1000)
            if config.DEBUG_MODE:
                page.screenshot(path=os.path.join(config.DEBUG_DIR, "step1b2_after_day.png"))
            # Ahora sí, selecciona la primera hora disponible en la lista.
            page.locator("text=/^\\d{1,2}:\\d{2}$/").first.click(timeout=10000, force=True)
            page.wait_for_timeout(500)
            # Confirma la selección si hay un botón de continuar/aceptar.
            for label in ["Continuar", "Continue", "Aceptar", "Accept", "Confirmar", "Confirm", "Ok"]:
                try:
                    page.get_by_text(label, exact=True).first.click(timeout=2000, force=True)
                    break
                except Exception:
                    continue
        page.wait_for_timeout(2000)

        if config.DEBUG_MODE:
            page.screenshot(path=os.path.join(config.DEBUG_DIR, "step2_how.png"))

        # Pantalla "¿Cómo?" -> "A recoger en local" / "Pick up in store"
        recoger_re = re.compile(r"A recoger en local|Pick up in store|Pickup", re.IGNORECASE)
        page.get_by_text(recoger_re).first.wait_for(state="visible", timeout=20000)
        page.get_by_text(recoger_re).first.click()
        page.wait_for_timeout(2500)

        if config.DEBUG_MODE:
            page.screenshot(path=os.path.join(config.DEBUG_DIR, "step3_menu.png"))
            with open(os.path.join(config.DEBUG_DIR, "step3_menu.html"), "w") as f:
                f.write(page.content())

        log(f"Carta cargada: {page.url}")

        if config.DEBUG_MODE:
            diag = page.evaluate("""
                () => {
                    const results = [];
                    document.querySelectorAll('*').forEach(el => {
                        if (el.scrollHeight > el.clientHeight + 50) {
                            results.push({
                                tag: el.tagName,
                                cls: el.className,
                                scrollHeight: el.scrollHeight,
                                clientHeight: el.clientHeight,
                                scrollTop: el.scrollTop
                            });
                        }
                    });
                    return {
                        scrollables: results,
                        windowScrollY: window.scrollY,
                        bodyScrollHeight: document.body.scrollHeight,
                        bodyClientHeight: document.body.clientHeight,
                    };
                }
            """)
            with open(os.path.join(config.DEBUG_DIR, "scroll_diagnosis.json"), "w") as f:
                json.dump(diag, f, indent=2)
            log(f"Diagnóstico de scroll: {json.dumps(diag)[:1000]}")

        # Scroll incremental por toda la carta, capturando texto en cada paso.
        # La lista está virtualizada (el DOM solo contiene el tramo visible),
        # así que document.body.scrollHeight no cambia con el scroll — el
        # criterio de "fin" es que el texto capturado deje de aportar
        # contenido nuevo durante varias rondas seguidas.
        seen_snippets = set()
        raw_chunks = []
        stable_rounds = 0
        max_rounds = 500

        def scroll_everything():
            """mouse.wheel no siempre llega al contenedor interno correcto en
            esta app; se fuerza el scroll vía JS directamente sobre .scrollbox
            (el contenedor real identificado por diagnóstico) y, como red de
            seguridad, sobre cualquier otro elemento desplazable."""
            return page.evaluate("""
                () => {
                    let moved = 0;
                    const box = document.querySelector('.scrollbox');
                    if (box) {
                        const before = box.scrollTop;
                        box.scrollTop += 600;
                        box.dispatchEvent(new Event('scroll', {bubbles: true}));
                        moved = box.scrollTop - before;
                    }
                    window.scrollBy(0, 600);
                    document.querySelectorAll('*').forEach(el => {
                        if (el.scrollHeight > el.clientHeight + 50) {
                            el.scrollTop += 600;
                        }
                    });
                    return moved;
                }
            """)

        # page.mouse.wheel debe apuntar sobre el contenedor real; se centra el
        # ratón sobre la zona de la carta antes de scrollear.
        page.mouse.move(250, 450)

        for round_i in range(max_rounds):
            # Muchos ticks PEQUEÑOS y reales (simulan la física de un scroll
            # físico) en vez de un salto grande de scrollTop: la app solo
            # recalcula su virtualización con eventos de scroll genuinos.
            for _ in range(6):
                page.mouse.wheel(0, 80)
                page.wait_for_timeout(40)
            text = scrape_category_text(page)
            if text not in seen_snippets:
                raw_chunks.append(text)
                seen_snippets.add(text)
                stable_rounds = 0
            else:
                stable_rounds += 1
            if config.DEBUG_MODE and round_i < 5:
                scroll_top = page.evaluate("document.querySelector('.scrollbox')?.scrollTop ?? -1")
                log(f"Ronda {round_i}: scrollbox.scrollTop = {scroll_top}")

            if stable_rounds > 15:
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

