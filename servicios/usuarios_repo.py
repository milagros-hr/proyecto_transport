import json, os
from pathlib import Path
from typing import Any, Dict, List, Optional

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
PASAJEROS_FILE = DATA_DIR / "pasajeros.json"
CONDUCTORES_FILE = DATA_DIR / "conductores.json"
VIAJES_FILE = DATA_DIR / "viajes.json"

def crear_directorio_data(): DATA_DIR.mkdir(parents=True, exist_ok=True)

def _leer_json(p: Path) -> List[Dict[str, Any]]:
    try:
        with p.open("r", encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, list) else []
    except FileNotFoundError:
        return []
    except json.JSONDecodeError:
        return []

def _guardar_json_atomic(p: Path, data: List[Dict[str, Any]]) -> bool:
    try:
        crear_directorio_data()
        tmp = p.with_suffix(p.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        tmp.replace(p)
        return True
    except Exception:
        return False

def archivo_por_tipo(tipo: str) -> Path:
    return PASAJEROS_FILE if tipo == "pasajero" else CONDUCTORES_FILE

def get_usuarios(tipo: str) -> List[Dict[str, Any]]:
    return _leer_json(archivo_por_tipo(tipo))

def set_usuarios(tipo: str, usuarios: List[Dict[str, Any]]) -> bool:
    return _guardar_json_atomic(archivo_por_tipo(tipo), usuarios)

def normalizar_correo(correo: str) -> str:
    return (correo or "").strip().lower()

def generar_id(datos: List[Dict[str, Any]]) -> int:
    return max([u.get("id", 0) for u in datos], default=0) + 1

def buscar_usuario_por_correo(correo: str, tipo: str) -> Optional[Dict[str, Any]]:
    correo = normalizar_correo(correo)
    for u in get_usuarios(tipo):
        if normalizar_correo(u.get("correo", "")) == correo:
            return u
    return None

def buscar_usuario_por_id(user_id: int, tipo: str) -> Optional[Dict[str, Any]]:
    """Busca por id dentro del tipo indicado (pasajero|conductor)."""
    for u in get_usuarios(tipo):
        if u.get("id") == user_id:
            return u
    return None

# (Opcional, si la necesitas para reportes, NO para auth)
def buscar_usuario_por_id_en_cualquier_tipo(user_id: int) -> Optional[Dict[str, Any]]:
    for tipo in ("pasajero", "conductor"):
        for u in get_usuarios(tipo):
            if u.get("id") == user_id:
                # Puedes devolver {'tipo': tipo, **u} si te sirve
                return u
    return None


def usuario_existe(correo: str, tipo: str) -> bool:
    return buscar_usuario_por_correo(correo, tipo) is not None

def obtener_estadisticas():
    p, c = get_usuarios("pasajero"), get_usuarios("conductor")
    return {"total_pasajeros": len(p), "total_conductores": len(c), "total_usuarios": len(p)+len(c)}

def listar_conductores_disponibles() -> List[Dict[str, Any]]:
    return get_usuarios("conductor")

def guardar_viaje(viaje: Dict[str, Any]) -> bool:
    v = _leer_json(VIAJES_FILE)
    v.append(viaje)
    return _guardar_json_atomic(VIAJES_FILE, v)


def get_viajes_por_pasajero(pasajero_id: int) -> List[Dict[str, Any]]:
    """Lee todos los viajes y devuelve solo los de un pasajero específico."""
    viajes = _leer_json(VIAJES_FILE)
    viajes_pasajero = [v for v in viajes if v.get("pasajero_id") == pasajero_id]
    return sorted(viajes_pasajero, key=lambda v: v.get("fecha", ""), reverse=True)


def actualizar_usuario(user_id: int, tipo: str, datos_actualizados: Dict[str, Any]) -> bool:
    """Actualiza los datos de un usuario y guarda el archivo."""
    usuarios = get_usuarios(tipo)
    usuario_encontrado = False
    for i, u in enumerate(usuarios):
        if u.get("id") == user_id:
            if "nombre" in datos_actualizados:
                usuarios[i]["nombre"] = datos_actualizados["nombre"]
            if "telefono" in datos_actualizados:
                usuarios[i]["telefono"] = datos_actualizados["telefono"]
            usuario_encontrado = True
            break

    if usuario_encontrado:
        return set_usuarios(tipo, usuarios)

    return False
