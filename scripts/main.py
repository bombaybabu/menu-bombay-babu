"""
Punto de entrada del monitor diario de la carta de Bombay Babu.

Flujo:
1. Extrae la carta actual (scraper.py) -> scripts/snapshots/latest.json
2. Compara con la ejecución anterior (differ.py)
3. Si hay cambios, regenera el bloque CATEGORIES de index.html vía Claude
   (publisher.py)
4. Rota el snapshot de hoy a "previous" para la próxima comparación
5. Sale con código 0 y escribe en stdout si hubo cambios, para que el
   workflow de GitHub Actions decida si hacer commit
"""
import os
import shutil
import sys

import config
import differ
import scraper


def main():
    try:
        items_today = scraper.run()
    except Exception as e:
        print(f"[main] ERROR en el scraping: {e}", file=sys.stderr)
        sys.exit(1)

    if not items_today:
        print("[main] Scraper no devolvió items, no se hace nada.", file=sys.stderr)
        sys.exit(1)

    has_changes, summary = differ.diff()

    if has_changes:
        print("[main] Cambios detectados:")
        print(summary)
        try:
            import publisher
            publisher.regenerate(items_today, summary)
            print("[main] index.html regenerado correctamente.")
        except Exception as e:
            print(f"[main] ERROR regenerando index.html: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        print("[main] Sin cambios respecto a la última revisión.")

    # Rota el snapshot para la próxima comparación
    if os.path.exists(config.TODAY_SNAPSHOT):
        shutil.copyfile(config.TODAY_SNAPSHOT, config.PREVIOUS_SNAPSHOT)

    # Señal para el workflow: si hubo cambios, imprime marcador en stdout
    if has_changes:
        print("::MENU_CHANGED::")


if __name__ == "__main__":
    main()
