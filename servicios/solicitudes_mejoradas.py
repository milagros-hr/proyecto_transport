# servicios/solicitudes_mejoradas.py
"""
Sistema de solicitudes con soporte para contraofertas
"""
import json
import os
from datetime import datetime, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
SOLICITUDES_FILE = DATA_DIR / "solicitudes.json"
CONTRAOFERTAS_FILE = DATA_DIR / "contraofertas.json"
VIAJES_FILE = DATA_DIR / "viajes.json"  # Agregamos esto

def _leer_json(path):
    try:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        print(f"⚠️ Error leyendo {path}:", e)
    return []

def _guardar_json(path, data):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"❌ Error guardando {path}:", e)
        return False

def calcular_precio(distancia_km):
    """
    Calcula el precio basado en distancia
    Fórmula: Base + (tarifa_por_km * distancia)
    """
    BASE = 3.00  # S/. 3.00 base
    TARIFA_KM = 1.20  # S/. 1.20 por km
    MAX_PRECIO = 40.00  # S/. 40.00 máximo
    
    precio = BASE + (TARIFA_KM * distancia_km)
    return min(precio, MAX_PRECIO)

def crear_solicitud_pasajero(pasajero_id, origen, destino, distancia, hora_viaje="ahora"):
    """
    Crea una solicitud de viaje desde el lado del pasajero
    """
    solicitudes = _leer_json(SOLICITUDES_FILE)
    
    nuevo_id = max([s.get('id', 0) for s in solicitudes], default=0) + 1
    precio_estimado = calcular_precio(distancia)

    ahora = datetime.now()
    fecha_partida_estimada = ahora
    if hora_viaje == "30_min":
        fecha_partida_estimada = ahora + timedelta(minutes=30)
    elif hora_viaje == "60_min":
        fecha_partida_estimada = ahora + timedelta(minutes=60)
    
    solicitud = {
        "id": nuevo_id,
        "pasajero_id": pasajero_id,
        "origen": origen,  # {"nombre": "Miraflores", "lat": -12.12, "lng": -77.02}
        "destino": destino,
        "distancia": round(distancia, 2),
        "precio_estandar": round(precio_estimado, 2),
        "estado": "pendiente",  # pendiente, aceptada, en_curso, completada, cancelada
        "conductor_id": None,
        "precio_acordado": None,
        "fecha_creacion": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "fecha_partida_estimada": fecha_partida_estimada.strftime("%Y-%m-%d %H:%M:%S"),
        "hora_seleccionada": hora_viaje,
        "fecha_actualizacion": None
    }
    
    solicitudes.append(solicitud)
    _guardar_json(SOLICITUDES_FILE, solicitudes)
    
    print(f"✅ Solicitud #{nuevo_id} creada: {origen['nombre']} → {destino['nombre']}, S/. {precio_estimado:.2f}")
    return solicitud

def obtener_solicitudes_activas():
    """
    Devuelve todas las solicitudes pendientes
    """
    solicitudes = _leer_json(SOLICITUDES_FILE)
    return [s for s in solicitudes if s.get('estado') == 'pendiente']

def obtener_solicitudes_cercanas(lat_conductor, lng_conductor, radio_km=10):
    """
    Filtra solicitudes dentro de un radio de distancia del conductor
    """
    from math import radians, sin, cos, sqrt, atan2
    
    def calcular_distancia(lat1, lon1, lat2, lon2):
        # Fórmula de Haversine
        R = 6371  # Radio de la Tierra en km
        dlat = radians(lat2 - lat1)
        dlon = radians(lon2 - lon1)
        a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        return R * c
    
    activas = obtener_solicitudes_activas()
    cercanas = []
    
    for sol in activas:
        origen = sol.get('origen', {})
        if 'lat' in origen and 'lng' in origen:
            dist = calcular_distancia(
                lat_conductor, lng_conductor,
                origen['lat'], origen['lng']
            )
            if dist <= radio_km:
                sol['distancia_conductor'] = round(dist, 2)
                cercanas.append(sol)
    
    # Ordenar por cercanía
    cercanas.sort(key=lambda x: x['distancia_conductor'])
    return cercanas

def crear_contraoferta(conductor_id, solicitud_id, precio_ofrecido, mensaje=""):
    """
    El conductor crea una contraoferta para una solicitud
    """
    contraofertas = _leer_json(CONTRAOFERTAS_FILE)
    
    # Verificar que la solicitud existe y está pendiente
    solicitudes = _leer_json(SOLICITUDES_FILE)
    solicitud = next((s for s in solicitudes if s['id'] == solicitud_id), None)
    
    if not solicitud or solicitud.get('estado') != 'pendiente':
        return None
    
    nuevo_id = max([c.get('id', 0) for c in contraofertas], default=0) + 1
    
    contraoferta = {
        "id": nuevo_id,
        "solicitud_id": solicitud_id,
        "conductor_id": conductor_id,
        "precio_ofrecido": round(precio_ofrecido, 2),
        "mensaje": mensaje,
        "estado": "pendiente",  # pendiente, aceptada, rechazada
        "fecha_creacion": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    contraofertas.append(contraoferta)
    _guardar_json(CONTRAOFERTAS_FILE, contraofertas)
    
    print(f"💰 Contraoferta #{nuevo_id} creada por conductor #{conductor_id}: S/. {precio_ofrecido:.2f}")
    return contraoferta

def aceptar_solicitud_directa(conductor_id, solicitud_id):
    """
    El conductor acepta el precio estándar directamente
    """
    solicitudes = _leer_json(SOLICITUDES_FILE)
    
    for sol in solicitudes:
        if sol['id'] == solicitud_id and sol.get('estado') == 'pendiente':
            sol['conductor_id'] = conductor_id
            sol['precio_acordado'] = sol['precio_estandar']
            sol['estado'] = 'aceptada'
            sol['fecha_actualizacion'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            _guardar_json(SOLICITUDES_FILE, solicitudes)
            print(f"✅ Solicitud #{solicitud_id} aceptada por conductor #{conductor_id}")
            return sol
    
    return None

def pasajero_acepta_contraoferta(pasajero_id, contraoferta_id):
    """
    El pasajero acepta una contraoferta específica
    """
    contraofertas = _leer_json(CONTRAOFERTAS_FILE)
    contraoferta = next((c for c in contraofertas if c['id'] == contraoferta_id), None)
    
    if not contraoferta or contraoferta.get('estado') != 'pendiente':
        return None
    
    # Actualizar contraoferta
    contraoferta['estado'] = 'aceptada'
    _guardar_json(CONTRAOFERTAS_FILE, contraofertas)
    
    # Actualizar solicitud
    solicitudes = _leer_json(SOLICITUDES_FILE)
    for sol in solicitudes:
        if sol['id'] == contraoferta['solicitud_id']:
            sol['conductor_id'] = contraoferta['conductor_id']
            sol['precio_acordado'] = contraoferta['precio_ofrecido']
            sol['estado'] = 'aceptada'
            sol['fecha_actualizacion'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            _guardar_json(SOLICITUDES_FILE, solicitudes)
            
            print(f"✅ Pasajero aceptó contraoferta #{contraoferta_id}, precio: S/. {contraoferta['precio_ofrecido']:.2f}")
            return sol
    
    return None

def obtener_contraofertas_pasajero(solicitud_id):
    """
    Obtiene todas las contraofertas pendientes para una solicitud
    """
    contraofertas = _leer_json(CONTRAOFERTAS_FILE)
    return [c for c in contraofertas 
            if c['solicitud_id'] == solicitud_id and c['estado'] == 'pendiente']

def cancelar_solicitud(solicitud_id, usuario_id, motivo=""):
    """
    Cancela una solicitud (puede ser pasajero o conductor)
    """
    solicitudes = _leer_json(SOLICITUDES_FILE)
    
    for sol in solicitudes:
        if sol['id'] == solicitud_id:
            if sol.get('estado') in ['pendiente', 'aceptada']:
                sol['estado'] = 'cancelada'
                sol['motivo_cancelacion'] = motivo
                sol['fecha_actualizacion'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                _guardar_json(SOLICITUDES_FILE, solicitudes)
                
                print(f"❌ Solicitud #{solicitud_id} cancelada por usuario #{usuario_id}")
                return True
    
    return False