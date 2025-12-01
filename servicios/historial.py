# servicios/historial.py
"""
Servicio de historial de viajes usando ListaEnlazada
Solo muestra viajes COMPLETADOS sin datos personales sensibles
"""

from estructuras.lista_enlazada import ListaEnlazada
from servicios.solicitudes_mejoradas import _leer_json, SOLICITUDES_FILE


def obtener_historial_pasajero(pasajero_id: int) -> ListaEnlazada:
    """
    Obtiene el historial de viajes completados de un pasajero.
    Solo incluye: origen, destino, fecha y precio (sin datos personales).
    
    Retorna una ListaEnlazada con los viajes.
    """
    solicitudes = _leer_json(SOLICITUDES_FILE)
    historial = ListaEnlazada()
    
    for s in solicitudes:
        if s.get('pasajero_id') == pasajero_id and s.get('estado') == 'completado':
            viaje_seguro = {
                'id': s.get('id'),
                'origen': s.get('origen', {}).get('nombre', 'Desconocido'),
                'destino': s.get('destino', {}).get('nombre', 'Desconocido'),
                'fecha': s.get('fecha_fin') or s.get('fecha_creacion', ''),
                'precio': s.get('precio_acordado') or s.get('precio_estandar', 0),
                'distancia': s.get('distancia', 0),
                'duracion_minutos': s.get('duracion_minutos', 0)
            }
            historial.insertar_final(viaje_seguro)
    
    return historial


def obtener_historial_conductor(conductor_id: int) -> ListaEnlazada:
    """
    Obtiene el historial de viajes completados de un conductor.
    Solo incluye: origen, destino, fecha y precio (sin datos personales).
    
    Retorna una ListaEnlazada con los viajes.
    """
    solicitudes = _leer_json(SOLICITUDES_FILE)
    historial = ListaEnlazada()
    
    for s in solicitudes:
        if s.get('conductor_id') == conductor_id and s.get('estado') == 'completado':
            viaje_seguro = {
                'id': s.get('id'),
                'origen': s.get('origen', {}).get('nombre', 'Desconocido'),
                'destino': s.get('destino', {}).get('nombre', 'Desconocido'),
                'fecha': s.get('fecha_fin') or s.get('fecha_creacion', ''),
                'precio': s.get('precio_acordado') or s.get('precio_estandar', 0),
                'distancia': s.get('distancia', 0),
                'duracion_minutos': s.get('duracion_minutos', 0)
            }
            historial.insertar_final(viaje_seguro)
    
    return historial


def contar_viajes_completados(historial: ListaEnlazada) -> int:
    """Cuenta los viajes en el historial"""
    return len(historial)


def calcular_total_gastado(historial: ListaEnlazada) -> float:
    """Calcula el total gastado/ganado en todos los viajes"""
    total = 0.0
    for viaje in historial.recorrer():
        total += viaje.get('precio', 0)
    return round(total, 2)


def calcular_distancia_total(historial: ListaEnlazada) -> float:
    """Calcula la distancia total recorrida"""
    total = 0.0
    for viaje in historial.recorrer():
        total += viaje.get('distancia', 0)
    return round(total, 2)
