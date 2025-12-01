# servicios/solicitudes_mejoradas.py
"""
Sistema de solicitudes con soporte para contraofertas
Usa la estructura COLA para manejar solicitudes en orden FIFO
(First In, First Out - Primero en llegar, primero en ser atendido)
"""
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from servicios.usuarios_repo import _guardar_json_atomic
from estructuras.cola import Cola  # ← ESTRUCTURA DE DATOS: COLA

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
SOLICITUDES_FILE = DATA_DIR / "solicitudes.json"
CONTRAOFERTAS_FILE = DATA_DIR / "contraofertas.json"
VIAJES_FILE = DATA_DIR / "viajes.json"

# ============================================
# COLA DE SOLICITUDES (Estructura de Datos)
# ============================================
# La cola garantiza que las solicitudes se procesen en orden FIFO:
# - El pasajero que solicita primero, aparece primero para los conductores
# - Esto es justo y eficiente para el sistema de transporte

cola_solicitudes = Cola()  # Cola en memoria para solicitudes pendientes


def _sincronizar_cola_desde_json():
    """
    Carga las solicitudes pendientes del JSON a la Cola (al iniciar el servidor).
    Mantiene el orden por fecha_creacion (FIFO).
    """
    global cola_solicitudes
    cola_solicitudes = Cola()  # Reiniciar cola
    
    solicitudes = _leer_json(SOLICITUDES_FILE)
    pendientes = [s for s in solicitudes if s.get('estado') == 'pendiente']
    
    # Ordenar por fecha de creación (más antigua primero = FIFO)
    pendientes.sort(key=lambda x: x.get('fecha_creacion', ''))
    
    for sol in pendientes:
        cola_solicitudes.encolar(sol)
    
    print(f"📋 Cola sincronizada: {len(cola_solicitudes)} solicitudes pendientes")


def _guardar_cola_a_json():
    """
    Persiste el estado actual de la cola al JSON.
    """
    solicitudes = _leer_json(SOLICITUDES_FILE)
    
    # Obtener IDs de solicitudes en la cola
    ids_en_cola = set()
    temp = []
    while not cola_solicitudes.esta_vacia():
        sol = cola_solicitudes.desencolar()
        ids_en_cola.add(sol.get('id'))
        temp.append(sol)
    
    # Re-encolar (mantener la cola intacta)
    for sol in temp:
        cola_solicitudes.encolar(sol)
    
    # Actualizar JSON con las solicitudes de la cola
    for sol in solicitudes:
        if sol.get('id') in ids_en_cola:
            # Buscar la versión actualizada en la cola
            for t in temp:
                if t.get('id') == sol.get('id'):
                    sol.update(t)
                    break
    
    _guardar_json(SOLICITUDES_FILE, solicitudes)

def _leer_json(path):
    try:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        print(f"⚠️ Error leyendo {path}:", e)
    return []

def _guardar_json(path, data):
    """
    Guarda JSON de forma segura con escritura atómica
    """
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        
        # Crear archivo temporal
        temp_path = str(path) + '.tmp'
        
        # Escribir en temporal
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        # Mover atómicamente (reemplazar el original)
        import shutil
        shutil.move(temp_path, path)
        
        return True
        
    except Exception as e:
        print(f"❌ Error guardando {path}:", e)
        # Limpiar temporal si existe
        try:
            temp_path = str(path) + '.tmp'
            if os.path.exists(temp_path):
                os.unlink(temp_path)
        except:
            pass
        return False

def calcular_precio(distancia_km):
    """
    Calcula el precio basado en distancia.
    Ajuste: Tarifas de mercado actual (Lima Metropolitana - Estándar/Plus).
    """
    # --- CONFIGURACIÓN DE TARIFAS ---
    
    # TARIFA_BASE: Arranque (S/. 4.50 es más común ahora)
    TARIFA_BASE = 4.50
    
    # TARIFA_POR_KM: Subimos a 2.30 para que sume rápido
    TARIFA_POR_KM = 2.30
    
    # TARIFA_MINIMA: Para no mover el auto por menos de 8 soles
    TARIFA_MINIMA = 8.00
    
    # --- CÁLCULO ---
    precio = TARIFA_BASE + (TARIFA_POR_KM * distancia_km)
    
    # Aplicar tarifa mínima
    precio_final = max(precio, TARIFA_MINIMA)
    
    # Redondear a 1 decimal (ej: 20.6)
    return round(precio_final, 1)

def crear_solicitud_pasajero(pasajero_id, origen, destino, distancia, hora_viaje="ahora"):
    """
    Crea una solicitud de viaje desde el lado del pasajero.
    
    ESTRUCTURA DE DATOS: Usa COLA para encolar la solicitud (FIFO).
    El pasajero que solicita primero será atendido primero.
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
        "origen": origen,
        "destino": destino,
        "distancia": round(distancia, 2),
        "precio_estandar": round(precio_estimado, 2),
        "estado": "pendiente",
        "conductor_id": None,
        "precio_acordado": None,
        "fecha_creacion": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "fecha_partida_estimada": fecha_partida_estimada.strftime("%Y-%m-%d %H:%M:%S"),
        "hora_seleccionada": hora_viaje,
        "fecha_actualizacion": None,
        "posicion_cola": len(cola_solicitudes) + 1  # Posición en la cola FIFO
    }
    
    # ✅ ENCOLAR: Agregar a la cola de solicitudes (FIFO)
    cola_solicitudes.encolar(solicitud)
    print(f"📋 Solicitud #{nuevo_id} encolada. Posición en cola: {solicitud['posicion_cola']}")
    
    # Guardar también en JSON para persistencia
    solicitudes.append(solicitud)
    _guardar_json(SOLICITUDES_FILE, solicitudes)
    
    print(f"✅ Solicitud #{nuevo_id} creada: {origen['nombre']} → {destino['nombre']}, S/. {precio_estimado:.2f}")
    return solicitud


def contar_contraofertas_pendientes_pasajero(pasajero_id: int) -> int:
    """
    Cuenta todas las contraofertas pendientes para todas las solicitudes activas
    de un pasajero.
    """
    try:
        solicitudes = _leer_json(SOLICITUDES_FILE)
        contraofertas_data = _leer_json(CONTRAOFERTAS_FILE)

        # 1. Encontrar IDs de solicitudes 'pendientes' de este pasajero
        #
        mis_solicitudes_ids = {
            s['id'] for s in solicitudes
            if s.get('pasajero_id') == pasajero_id and s.get('estado') == 'pendiente'
        }

        if not mis_solicitudes_ids:
            return 0

        # 2. Contar contraofertas 'pendientes' para esas solicitudes
        #
        conteo = 0
        for c in contraofertas_data:
            if c.get('solicitud_id') in mis_solicitudes_ids and c.get('estado') == 'pendiente':
                conteo += 1

        return conteo

    except Exception as e:
        print(f"❌ Error contando contraofertas: {e}")
        return 0


def pasajero_rechaza_contraoferta(pasajero_id, contraoferta_id):
    """
    El pasajero rechaza una contraoferta.
    La marca como 'rechazada' en contraofertas.json.
    """
    contraofertas = _leer_json(CONTRAOFERTAS_FILE)
    contraoferta_encontrada = False

    # Podríamos añadir una validación extra para asegurar que el pasajero_id
    # es el dueño de la solicitud original, pero por ahora esto es funcional.

    for c in contraofertas:
        if c['id'] == contraoferta_id and c.get('estado') == 'pendiente':
            c['estado'] = 'rechazada'
            c['fecha_actualizacion'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            contraoferta_encontrada = True
            break

    if contraoferta_encontrada:
        _guardar_json(CONTRAOFERTAS_FILE, contraofertas)
        print(f"👎 Contraoferta #{contraoferta_id} marcada como RECHAZADA.")
        return True

    return False



def obtener_solicitudes_activas():
    """
    Devuelve todas las solicitudes pendientes EN ORDEN FIFO (usando la Cola).
    
    ESTRUCTURA DE DATOS: Recorre la Cola sin modificarla para obtener
    las solicitudes en el orden en que llegaron.
    """
    # Si la cola está vacía, sincronizar desde JSON
    if cola_solicitudes.esta_vacia():
        _sincronizar_cola_desde_json()
    
    # Recorrer la cola sin modificarla (desencolar y re-encolar)
    solicitudes_ordenadas = []
    temp = []
    
    while not cola_solicitudes.esta_vacia():
        sol = cola_solicitudes.desencolar()
        # Solo incluir las que siguen pendientes
        if sol.get('estado') == 'pendiente':
            solicitudes_ordenadas.append(sol)
        temp.append(sol)
    
    # Re-encolar todo para mantener la cola intacta
    for sol in temp:
        if sol.get('estado') == 'pendiente':
            cola_solicitudes.encolar(sol)
    
    print(f"📋 Solicitudes activas (FIFO): {len(solicitudes_ordenadas)} en cola")
    return solicitudes_ordenadas


def obtener_solicitudes_cercanas(lat_conductor, lng_conductor, radio_km=10):
    """
    Filtra solicitudes dentro de un radio de distancia del conductor.
    
    IMPORTANTE: Mantiene el orden FIFO de la cola, pero filtra por cercanía.
    Las solicitudes más antiguas aparecen primero dentro del radio.
    """
    from math import radians, sin, cos, sqrt, atan2
    
    # Factor de corrección: distancia real por carretera ≈ 1.4x distancia aérea
    FACTOR_CORRECCION = 1.4
    
    def calcular_distancia(lat1, lon1, lat2, lon2):
        R = 6371
        dlat = radians(lat2 - lat1)
        dlon = radians(lon2 - lon1)
        a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        distancia_aerea = R * c
        return round(distancia_aerea * FACTOR_CORRECCION, 2)
    
    # Obtener solicitudes en orden FIFO
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
    
    # NO reordenar por distancia - mantener orden FIFO (primero en llegar)
    # El conductor ve primero las solicitudes más antiguas dentro de su radio
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

def _desencolar_solicitud(solicitud_id):
    """
    ESTRUCTURA DE DATOS: Remueve una solicitud de la Cola cuando es aceptada.
    Esto implementa el DESENCOLAR del FIFO - la solicitud sale de la cola.
    """
    global cola_solicitudes
    temp = []
    removida = None
    
    while not cola_solicitudes.esta_vacia():
        sol = cola_solicitudes.desencolar()
        if sol.get('id') == solicitud_id:
            removida = sol
            print(f"📤 Solicitud #{solicitud_id} DESENCOLADA (salió de la cola FIFO)")
        else:
            temp.append(sol)
    
    # Re-encolar las que no fueron removidas
    for sol in temp:
        cola_solicitudes.encolar(sol)
    
    return removida


def aceptar_solicitud_directa(conductor_id, solicitud_id):
    """
    El conductor acepta el precio estándar directamente.
    
    ESTRUCTURA DE DATOS: Al aceptar, la solicitud se DESENCOLA (sale de la cola FIFO).
    """
    solicitudes = _leer_json(SOLICITUDES_FILE)
    
    for sol in solicitudes:
        if sol['id'] == solicitud_id and sol.get('estado') == 'pendiente':
            sol['conductor_id'] = conductor_id
            sol['precio_acordado'] = sol['precio_estandar']
            sol['estado'] = 'aceptada'
            sol['fecha_actualizacion'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # ✅ DESENCOLAR: Remover de la cola FIFO
            _desencolar_solicitud(solicitud_id)
            
            _guardar_json(SOLICITUDES_FILE, solicitudes)
            print(f"✅ Solicitud #{solicitud_id} aceptada por conductor #{conductor_id}")
            return sol
    
    return None

def pasajero_acepta_contraoferta(pasajero_id, contraoferta_id):
    """
    El pasajero acepta una contraoferta específica y el viaje queda CONFIRMADO.
    
    ESTRUCTURA DE DATOS: Al confirmar, la solicitud se DESENCOLA (sale de la cola FIFO).
    """
    # 1) Cargar contraofertas y buscar la elegida
    contraofertas = _leer_json(CONTRAOFERTAS_FILE)

    contraoferta = next(
        (c for c in contraofertas if int(c.get('id', -1)) == int(contraoferta_id)),
        None
    )

    if not contraoferta or contraoferta.get('estado') != 'pendiente':
        return None

    solicitud_id = contraoferta.get('solicitud_id')
    conductor_id = contraoferta.get('conductor_id')
    precio_ofrecido = contraoferta.get('precio_ofrecido')  # ✅ KEY CORRECTA

    # 2) Cargar solicitudes y validar pertenencia
    solicitudes = _leer_json(SOLICITUDES_FILE)
    sol = next((s for s in solicitudes if s.get('id') == solicitud_id), None)

    if not sol:
        return None

    if sol.get('pasajero_id') != pasajero_id:
        # Seguridad: no puede aceptar ofertas de otra solicitud ajena
        return None

    if sol.get('estado') != 'pendiente':
        # Si ya no está pendiente, no debería aceptar contraofertas
        return None

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 3) Actualizar solicitud (viaje)
    sol['conductor_id'] = conductor_id
    sol['precio_acordado'] = float(precio_ofrecido) if precio_ofrecido is not None else sol.get('precio_estandar')
    sol['estado'] = 'confirmado'
    sol['fecha_actualizacion'] = now
    sol['fecha_confirmacion'] = now

    # 4) Actualizar estados de contraofertas: aceptar una, rechazar las demás pendientes
    for c in contraofertas:
        if c.get('solicitud_id') == solicitud_id and c.get('estado') == 'pendiente':
            c['estado'] = 'rechazada'
            c['fecha_actualizacion'] = now

    contraoferta['estado'] = 'aceptada'
    contraoferta['fecha_actualizacion'] = now

    # ✅ DESENCOLAR: Remover de la cola FIFO (ya no está pendiente)
    _desencolar_solicitud(solicitud_id)

    # 5) Guardar atómico (más seguro)
    _guardar_json_atomic(CONTRAOFERTAS_FILE, contraofertas)
    _guardar_json_atomic(SOLICITUDES_FILE, solicitudes)

    print(f"✅ ¡MATCH! Viaje #{sol['id']} confirmado por contraoferta. Precio: {sol['precio_acordado']}")
    return sol


def obtener_contraofertas_pasajero(solicitud_id):
    """
    Obtiene todas las contraofertas pendientes para una solicitud
    """
    contraofertas = _leer_json(CONTRAOFERTAS_FILE)
    return [c for c in contraofertas 
            if c['solicitud_id'] == solicitud_id and c['estado'] == 'pendiente']


def cancelar_solicitud_detalle(solicitud_id, usuario_id, motivo=""):
    """
    Cancela una solicitud (pasajero o conductor)
    Devuelve: (ok: bool, payload: dict|str)
    """
    solicitudes = _leer_json(SOLICITUDES_FILE)

    try:
        sid = int(solicitud_id)
        uid = int(usuario_id)
    except Exception:
        return (False, "solicitud_id/usuario_id inválido")

    for sol in solicitudes:
        try:
            if int(sol.get("id", -1)) != sid:
                continue
        except Exception:
            continue

        pasajero_id = sol.get("pasajero_id")
        conductor_id = sol.get("conductor_id")

        try:
            pasajero_id = int(pasajero_id) if pasajero_id is not None else None
        except Exception:
            pass
        try:
            conductor_id = int(conductor_id) if conductor_id is not None else None
        except Exception:
            pass

        if uid not in [pasajero_id, conductor_id]:
            return (False, "No autorizado para cancelar esta solicitud")

        estado = (sol.get("estado") or "").lower()
        estados_cancelables = ["pendiente", "aceptada", "confirmado", "en_curso"]  # ✅ Agregar en_curso

        if estado not in estados_cancelables:
            return (False, f"No se puede cancelar en estado: {estado}")

        quien = "pasajero" if uid == pasajero_id else "conductor"

        sol["estado"] = f"cancelado_{quien}"
        sol["motivo_cancelacion"] = motivo or ""
        sol["fecha_cancelacion"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sol["fecha_actualizacion"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # ✅ Guardar ID del conductor antes de limpiar
        if conductor_id:
            sol["conductor_id_cancelado"] = conductor_id

        sol["conductor_id"] = None
        sol["precio_acordado"] = None

        _guardar_json_atomic(SOLICITUDES_FILE, solicitudes)
        print(f"✅ Solicitud #{sid} cancelada por {quien}. Estado: cancelado_{quien}")
        return (True, sol)

    return (False, "Solicitud no encontrada")


def cancelar_solicitud(solicitud_id, usuario_id, motivo=""):
    """
    Compatibilidad: devuelve SOLO bool (para código antiguo).
    """
    solicitudes = _leer_json(SOLICITUDES_FILE)
    for sol in solicitudes:
            if str(sol.get('id')) == str(solicitud_id):
                if sol.get('estado') in ['pendiente', 'aceptada', 'confirmado', 'en_curso']:
                    # ✅ Guardar conductor_id antes de limpiarlo
                    if sol.get('conductor_id'):
                        sol['conductor_id_cancelado'] = sol['conductor_id']
                    
                    sol['estado'] = 'cancelado_pasajero'
                    sol['motivo_cancelacion'] = motivo
                    sol['fecha_actualizacion'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    sol['fecha_cancelacion'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    sol['conductor_id'] = None
                    _guardar_json(SOLICITUDES_FILE, solicitudes)
                    print(f"✅ Solicitud #{solicitud_id} cancelada. Conductor guardado: {sol.get('conductor_id_cancelado')}")
                    return True
    return False


def obtener_ofertas_completas_pasajero(pasajero_id):
    """
    Obtiene TODAS las ofertas para un pasajero:
    - Contraofertas con precio personalizado (pendientes)
    - Ofertas aceptadas directamente al precio estándar (estado='aceptada')
    """
    try:
        solicitudes = _leer_json(SOLICITUDES_FILE)
        contraofertas_data = _leer_json(CONTRAOFERTAS_FILE)

        # Encontrar solicitudes activas del pasajero (pendiente O aceptada)
        mis_solicitudes_ids = {
            s['id'] for s in solicitudes
            if s.get('pasajero_id') == pasajero_id 
            and s.get('estado') in ['pendiente', 'aceptada']
        }

        if not mis_solicitudes_ids:
            return []

        resultado = []

        for sol in solicitudes:
            if sol['id'] not in mis_solicitudes_ids:
                continue

            ofertas = []

            # 1. Agregar contraofertas pendientes
            contraofertas = [
                c for c in contraofertas_data
                if c.get('solicitud_id') == sol['id'] and c.get('estado') == 'pendiente'
            ]

            for contra in contraofertas:
                from servicios.usuarios_repo import buscar_usuario_por_id
                conductor = buscar_usuario_por_id(contra['conductor_id'], 'conductor')
                if conductor:
                    contra['conductor_nombre'] = conductor.get('nombre', 'Conductor')
                    contra['conductor_vehiculo'] = f"{conductor.get('modelo', 'N/D')} {conductor.get('color', '')} - {conductor.get('placa', '')}"
                    contra['conductor_telefono'] = conductor.get('telefono', 'N/A')
                    contra['conductor_calificacion'] = 4.5
                    contra['tipo_oferta'] = 'contraoferta'
                    ofertas.append(contra)

            # 2. Si la solicitud fue aceptada directamente, agregar como "oferta"
            if sol.get('estado') == 'aceptada' and sol.get('conductor_id'):
                from servicios.usuarios_repo import buscar_usuario_por_id
                conductor = buscar_usuario_por_id(sol['conductor_id'], 'conductor')
                
                if conductor:
                    oferta_directa = {
                        'id': f"directa_{sol['id']}",
                        'solicitud_id': sol['id'],
                        'conductor_id': sol['conductor_id'],
                        'conductor_nombre': conductor.get('nombre', 'Conductor'),
                        'conductor_vehiculo': f"{conductor.get('modelo', 'N/D')} {conductor.get('color', '')} - {conductor.get('placa', '')}",
                        'conductor_telefono': conductor.get('telefono', 'N/A'),
                        'conductor_calificacion': 4.5,
                        'precio_ofrecido': sol.get('precio_acordado') or sol.get('precio_estandar'),
                        'mensaje': '✅ Este conductor aceptó tu solicitud al precio estándar',
                        'tipo_oferta': 'aceptacion_directa',
                        'estado': 'aceptada',
                        'fecha_creacion': sol.get('fecha_actualizacion') or sol.get('fecha_creacion')
                    }
                    ofertas.append(oferta_directa)

            if ofertas:
                resultado.append({
                    "solicitud": sol,
                    "contraofertas": ofertas  # Mantener nombre "contraofertas" para compatibilidad
                })

        return resultado

    except Exception as e:
        print(f"❌ Error obteniendo ofertas completas: {e}")
        import traceback
        traceback.print_exc()
        return []
    

def obtener_viajes_conductor(conductor_id):
    """
    Obtiene los viajes del conductor en diferentes estados:
    - confirmado: El pasajero confirmó, listo para iniciar
    - en_curso: Viaje iniciado por el conductor
    - completado: Viaje finalizado
    """
    try:
        solicitudes = _leer_json(SOLICITUDES_FILE)
        
        viajes = [
            s for s in solicitudes
            if s.get('conductor_id') == conductor_id
            and s.get('estado') in ['confirmado', 'en_curso', 'completado', 'cancelado_pasajero']
        ]
        orden = {'cancelado_pasajero': 0, 'confirmado': 1, 'en_curso': 2, 'completado': 3}
        viajes.sort(key=lambda v: orden.get(v.get('estado'), 9))

        
        # Enriquecer con datos del pasajero
        from servicios.usuarios_repo import buscar_usuario_por_id
        for viaje in viajes:
            pasajero = buscar_usuario_por_id(viaje['pasajero_id'], 'pasajero')
            if pasajero:
                viaje['pasajero_nombre'] = pasajero.get('nombre', 'Pasajero')
                viaje['pasajero_telefono'] = pasajero.get('telefono', 'N/A')
        
        # Ordenar: primero confirmados, luego en_curso, luego completados
        orden = {'confirmado': 0, 'en_curso': 1, 'completado': 2}
        viajes.sort(key=lambda v: orden.get(v.get('estado'), 3))
        
        return viajes
        
    except Exception as e:
        print(f"❌ Error obteniendo viajes del conductor: {e}")
        return []


def iniciar_viaje_conductor(conductor_id, solicitud_id):
    """
    El conductor inicia un viaje confirmado
    """
    try:
        solicitudes = _leer_json(SOLICITUDES_FILE)
        viaje_encontrado = False
        
        print(f"🔍 Buscando solicitud #{solicitud_id} para conductor #{conductor_id}")
        
        for i, sol in enumerate(solicitudes):
            print(f"  - Revisando solicitud #{sol.get('id')}: estado={sol.get('estado')}, conductor={sol.get('conductor_id')}")
            
            if (sol.get('id') == solicitud_id 
                and sol.get('conductor_id') == conductor_id
                and sol.get('estado') == 'confirmado'):
                
                solicitudes[i]['estado'] = 'en_curso'
                solicitudes[i]['fecha_inicio'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                viaje_encontrado = True
                
                print(f"✅ Viaje #{solicitud_id} iniciado. Nuevo estado: en_curso")
                break
        
        if viaje_encontrado:
            if _guardar_json(SOLICITUDES_FILE, solicitudes):
                print(f"✅ Cambios guardados correctamente")
                # Recargar para confirmar
                solicitudes_verificar = _leer_json(SOLICITUDES_FILE)
                viaje_actualizado = next((s for s in solicitudes_verificar if s.get('id') == solicitud_id), None)
                if viaje_actualizado:
                    print(f"✅ Verificación: Estado actual = {viaje_actualizado.get('estado')}")
                    return viaje_actualizado
            else:
                print("❌ Error al guardar cambios")
        else:
            print(f"❌ Viaje no encontrado o no está en estado 'confirmado'")
        
        return None
        
    except Exception as e:
        print(f"❌ Error iniciando viaje: {e}")
        import traceback
        traceback.print_exc()
        return None


def finalizar_viaje_conductor(conductor_id, solicitud_id):
    """
    El conductor finaliza un viaje en curso
    """
    try:
        solicitudes = _leer_json(SOLICITUDES_FILE)
        viaje_encontrado = False
        
        print(f"🔍 Buscando viaje en curso #{solicitud_id} para conductor #{conductor_id}")
        
        for i, sol in enumerate(solicitudes):
            print(f"  - Revisando solicitud #{sol.get('id')}: estado={sol.get('estado')}, conductor={sol.get('conductor_id')}")
            
            if sol.get('id') == solicitud_id and sol.get('conductor_id') == conductor_id:
                estado_actual = sol.get('estado')
                print(f"  - Solicitud encontrada. Estado actual: {estado_actual}")
                
                if estado_actual == 'en_curso':
                    solicitudes[i]['estado'] = 'completado'
                    solicitudes[i]['fecha_fin'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    
                    # Calcular duración del viaje
                    if sol.get('fecha_inicio'):
                        try:
                            inicio = datetime.strptime(sol['fecha_inicio'], "%Y-%m-%d %H:%M:%S")
                            fin = datetime.strptime(solicitudes[i]['fecha_fin'], "%Y-%m-%d %H:%M:%S")
                            duracion_minutos = (fin - inicio).total_seconds() / 60
                            solicitudes[i]['duracion_minutos'] = round(duracion_minutos, 1)
                            print(f"  - Duración calculada: {duracion_minutos:.1f} min")
                        except Exception as e:
                            print(f"  - Error calculando duración: {e}")
                    
                    viaje_encontrado = True
                    print(f"✅ Viaje #{solicitud_id} finalizado. Nuevo estado: completado")
                    break
                else:
                    print(f"❌ Viaje no está en curso (estado actual: {estado_actual})")
                    return None
        
        if viaje_encontrado:
            if _guardar_json(SOLICITUDES_FILE, solicitudes):
                print(f"✅ Cambios guardados correctamente")
                # Recargar para confirmar
                solicitudes_verificar = _leer_json(SOLICITUDES_FILE)
                viaje_actualizado = next((s for s in solicitudes_verificar if s.get('id') == solicitud_id), None)
                if viaje_actualizado:
                    print(f"✅ Verificación: Estado final = {viaje_actualizado.get('estado')}")
                    return viaje_actualizado
            else:
                print("❌ Error al guardar cambios")
        else:
            print(f"❌ Viaje no encontrado")
        
        return None
        
    except Exception as e:
        print(f"❌ Error finalizando viaje: {e}")
        import traceback
        traceback.print_exc()
        return None



def cancelar_viaje_conductor(conductor_id, solicitud_id, motivo=""):
    """
    El conductor cancela un viaje confirmado o en curso
    """
    try:
        solicitudes = _leer_json(SOLICITUDES_FILE)
        
        for sol in solicitudes:
            if (sol.get('id') == solicitud_id 
                and sol.get('conductor_id') == conductor_id
                and sol.get('estado') in ['confirmado', 'en_curso']):
                
                sol['estado'] = 'cancelado_conductor'
                sol['fecha_cancelacion'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                sol['motivo_cancelacion'] = motivo
                sol['conductor_id_cancelado'] = conductor_id  # ✅ GUARDAR antes de limpiar
                sol['conductor_id'] = None
                sol['precio_acordado'] = None
                
                _guardar_json_atomic(SOLICITUDES_FILE, solicitudes)
                
                print(f"❌ Viaje #{solicitud_id} cancelado por conductor #{conductor_id}")
                return sol
        
        return None
        
    except Exception as e:
        print(f"❌ Error cancelando viaje: {e}")
        return None
    
def obtener_cancelaciones_pendientes_conductor(conductor_id: int):
    """
    Devuelve solicitudes canceladas por pasajero que pertenecían a este conductor
    y que aún no han sido vistas por él.
    """
    try:
        solicitudes = _leer_json(SOLICITUDES_FILE)
        cid = int(conductor_id)

        pendientes = []
        for s in solicitudes:
            estado = (s.get("estado") or "").lower()
            if estado != "cancelado_pasajero":
                continue

            # Si ya fue vista por el conductor, no mostrarla
            if s.get("cancelacion_vista_por_conductor"):
                continue

            # Buscar en conductor_id_cancelado (donde guardamos el ID antes de limpiarlo)
            c2 = s.get("conductor_id_cancelado")
            try:
                c2 = int(c2) if c2 is not None else None
            except:
                pass

            if c2 == cid:
                s["tipo"] = "cancelacion"
                pendientes.append(s)

        return pendientes

    except Exception as e:
        print(f"❌ Error obteniendo cancelaciones pendientes conductor: {e}")
        import traceback; traceback.print_exc()
        return []


def marcar_cancelacion_vista_conductor(conductor_id: int, solicitud_id: int):
    """
    Marca una cancelación como vista por el conductor para que no vuelva a aparecer.
    """
    try:
        solicitudes = _leer_json(SOLICITUDES_FILE)
        cid = int(conductor_id)
        sid = int(solicitud_id)

        for s in solicitudes:
            if s.get("id") == sid:
                c2 = s.get("conductor_id_cancelado")
                try:
                    c2 = int(c2) if c2 is not None else None
                except:
                    pass
                
                if c2 == cid:
                    s["cancelacion_vista_por_conductor"] = True
                    s["fecha_vista_conductor"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    _guardar_json_atomic(SOLICITUDES_FILE, solicitudes)
                    print(f"✅ Cancelación #{sid} marcada como vista por conductor #{cid}")
                    return True
        return False
    except Exception as e:
        print(f"❌ Error marcando cancelación como vista: {e}")
        return False


def _leer_json(path):
    try:
        if os.path.exists(path):
            # Si el archivo está vacío, devolver []
            if os.path.getsize(path) == 0:
                return []
            with open(path, 'r', encoding='utf-8') as f:
                contenido = f.read().strip()
                if not contenido:
                    return []
                return json.loads(contenido)
    except Exception as e:
        print(f"⚠️ Error leyendo {path}: {e}")
        # Intento de "auto-reparación": dejarlo como []
        try:
            _guardar_json(path, [])
        except:
            pass
    return []
