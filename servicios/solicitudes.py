from estructuras.cola import Cola
import json, os, time

cola_solicitudes = Cola()
BASE_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
SOLICITUDES_FILE = os.path.join(BASE_DIR, 'solicitudes.json')
VIAJES_FILE = os.path.join(BASE_DIR, 'viajes.json')

# Agregar esta función al archivo servicios/solicitudes.py

import time
import uuid

def generar_solicitud_id():
    """Genera un ID único para solicitudes"""
    return f"sol-{int(time.time()*1000)}-{uuid.uuid4().hex[:8]}"

# Modificar la función encolar_solicitud para agregar ID automáticamente
def encolar_solicitud(solicitud: dict):
    """Encola una solicitud agregando un ID único si no existe"""
    if 'solicitud_id' not in solicitud and 'id' not in solicitud:
        solicitud['solicitud_id'] = generar_solicitud_id()
    cola_solicitudes.encolar(solicitud)
    return solicitud.get('solicitud_id') or solicitud.get('id')



def _leer_json(path):
    try:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        print("⚠️ Error leyendo JSON:", e)
    return []

def _guardar_json(path, data):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print("❌ Error guardando JSON:", e)
        return False

def listar_solicitudes():
    """Combina solicitudes en memoria + archivo + viajes.json"""
    resultado = []
    try:
        if hasattr(cola_solicitudes, "to_list"):
            resultado = cola_solicitudes.to_list() or []
        else:
            temp = []
            while len(cola_solicitudes):
                temp.append(cola_solicitudes.desencolar())
            for s in temp:
                cola_solicitudes.encolar(s)
            resultado = temp

        # Añadir las guardadas en solicitudes.json
        archivo = _leer_json(SOLICITUDES_FILE)
        for s in archivo:
            if not any(str(r.get("id")) == str(s.get("id")) for r in resultado):
                resultado.append(s)

        # Añadir también desde viajes.json (sin conductor)
        viajes = _leer_json(VIAJES_FILE)
        for v in viajes:
            if v.get('conductor_id') in (None, 0, ''):
                if not any(str(r.get("id")) == str(v.get("id")) for r in resultado):
                    resultado.append(v)
        return resultado
    except Exception as e:
        print("❌ Error en listar_solicitudes:", e)
        return []

def leer_solicitudes():
    """Para el endpoint /api/solicitudes_cercanas"""
    return listar_solicitudes()

def aceptar_solicitud_por_id(solicitud_id):
    """Busca y elimina una solicitud de la cola o archivo."""
    aceptada = None
    temp = []
    try:
        while len(cola_solicitudes):
            s = cola_solicitudes.desencolar()
            sid = s.get("solicitud_id") or s.get("viaje_id") or s.get("id")
            if str(sid) == str(solicitud_id) and aceptada is None:
                aceptada = s
                continue
            temp.append(s)
    except Exception as e:
        print("Error aceptar_solicitud_por_id:", e)
    finally:
        for item in temp:
            try:
                cola_solicitudes.encolar(item)
            except Exception:
                pass

    # Quitar del archivo también
    data = _leer_json(SOLICITUDES_FILE)
    data = [d for d in data if str(d.get("id")) != str(solicitud_id)]
    _guardar_json(SOLICITUDES_FILE, data)
    return aceptada
