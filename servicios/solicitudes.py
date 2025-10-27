from estructuras.cola import Cola
import json
import os
import time

# Cola global del módulo (simple para la demo)
cola_solicitudes = Cola()

def encolar_solicitud(solicitud: dict):
    cola_solicitudes.encolar(solicitud)

def siguiente_solicitud():
    return cola_solicitudes.desencolar()

def solicitudes_pendientes():
    return len(cola_solicitudes)

def listar_solicitudes():
    """
    Devuelve una copia no destructiva de las solicitudes en cola.
    Intenta usar helpers del objeto Cola o, si no existen, hace un
    desencolar/reencolar temporal (preserva orden).
    También añade como fallback los viajes pendientes en data/viajes.json
    (útil para pruebas cuando ya hay viajes guardados).
    """
    try:
        # 1) Obtener lista desde la cola si es posible
        if hasattr(cola_solicitudes, "to_list"):
            cola_list = cola_solicitudes.to_list() or []
        elif hasattr(cola_solicitudes, "listar"):
            cola_list = cola_solicitudes.listar() or []
        else:
            cola_list = None
            for attr in ("items", "_items", "_data", "data", "cola", "lista"):
                arr = getattr(cola_solicitudes, attr, None)
                if arr is not None:
                    try:
                        cola_list = list(arr)
                        break
                    except Exception:
                        pass
            if cola_list is None:
                temp = []
                while len(cola_solicitudes):
                    temp.append(cola_solicitudes.desencolar())
                for s in temp:
                    cola_solicitudes.encolar(s)
                cola_list = temp

        resultado = list(cola_list)

        # 2) Fallback: añadir viajes pendientes desde data/viajes.json si existen
        try:
            base = os.path.join(os.path.dirname(__file__), '..', 'data', 'viajes.json')
            base = os.path.normpath(base)
            if os.path.exists(base):
                with open(base, 'r', encoding='utf-8') as f:
                    viajes = json.load(f)
                for v in viajes:
                    if v.get('conductor_id') in (None, 0, ''):
                        sol = {
                            "viaje_id": v.get("id"),
                            "pasajero_id": v.get("pasajero_id"),
                            "origen": v.get("origen"),
                            "destino": v.get("destino"),
                            "fuente": "viajes.json"
                        }
                        if not any(str(r.get('viaje_id')) == str(sol['viaje_id']) for r in resultado if r.get('viaje_id') is not None):
                            resultado.append(sol)
        except Exception:
            pass

        return resultado
    except Exception:
        return []

def generar_solicitud_id():
    return f"sol-{int(time.time()*1000)}"

def aceptar_solicitud_por_id(solicitud_id):
    """
    Busca y remueve la primera solicitud cuyo campo 'solicitud_id' o 'viaje_id' o 'id' coincide.
    Devuelve la solicitud removida o None.
    """
    aceptada = None
    temp = []
    try:
        while len(cola_solicitudes):
            s = cola_solicitudes.desencolar()
            sid = None
            if isinstance(s, dict):
                sid = s.get("solicitud_id") or s.get("viaje_id") or s.get("id")
            if sid is not None and str(sid) == str(solicitud_id) and aceptada is None:
                aceptada = s
                continue
            temp.append(s)
    except Exception:
        pass
    finally:
        for item in temp:
            try:
                cola_solicitudes.encolar(item)
            except Exception:
                pass
    return aceptada