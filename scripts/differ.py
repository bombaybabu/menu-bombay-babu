"""
Compara el snapshot de hoy con el de la ejecución anterior y produce un
resumen legible de los cambios (platos nuevos, retirados, precio cambiado).
"""
import json
import os

import config


def load(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def key(item):
    return (item.get("category"), item.get("name"))


def diff():
    today = load(config.TODAY_SNAPSHOT)
    previous = load(config.PREVIOUS_SNAPSHOT)

    today_map = {key(i): i for i in today}
    prev_map = {key(i): i for i in previous}

    added = [today_map[k] for k in today_map if k not in prev_map]
    removed = [prev_map[k] for k in prev_map if k not in today_map]
    changed = []
    for k in today_map:
        if k in prev_map and today_map[k].get("price") != prev_map[k].get("price"):
            changed.append({
                "category": k[0],
                "name": k[1],
                "old_price": prev_map[k].get("price"),
                "new_price": today_map[k].get("price"),
            })

    lines = []
    for it in added:
        lines.append(f"+ Nuevo: [{it['category']}] {it['name']} — {it['price']}")
    for it in removed:
        lines.append(f"- Retirado: [{it['category']}] {it['name']}")
    for it in changed:
        lines.append(
            f"~ Precio cambiado: [{it['category']}] {it['name']} — "
            f"{it['old_price']} → {it['new_price']}"
        )

    summary = "\n".join(lines) if lines else ""
    has_changes = bool(lines)
    return has_changes, summary


if __name__ == "__main__":
    has_changes, summary = diff()
    print("CAMBIOS DETECTADOS" if has_changes else "SIN CAMBIOS")
    if summary:
        print(summary)
