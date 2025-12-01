# scripts/set_temp_password.py
import json
from pathlib import Path
from werkzeug.security import generate_password_hash

BASE = Path(__file__).resolve().parents[1]
DATA = BASE / "data"

def set_temp(file_name, temp="Temporal123"):
    p = DATA / file_name
    data = json.loads(p.read_text(encoding="utf-8")) if p.exists() else []
    changed = False
    for u in data:
        if not u.get("password_hash"):
            u["password_hash"] = generate_password_hash(
                temp, method="pbkdf2:sha256", salt_length=16
            )
            changed = True
    if changed:
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Actualizado: {file_name} -> contraseña temporal '{temp}'")
    else:
        print(f"Sin cambios: {file_name}")

if __name__ == "__main__":
    set_temp("pasajeros.json")
    set_temp("conductores.json")
