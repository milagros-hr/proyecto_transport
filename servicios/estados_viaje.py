# servicios/estados_viaje.py
"""
Sistema completo de estados para los viajes
"""
from enum import Enum
from datetime import datetime

class EstadoViaje(Enum):
    """Estados posibles de un viaje"""
    PENDIENTE = "pendiente"              # Solicitud creada
    CON_OFERTAS = "con_ofertas"          # Hay contraofertas disponibles
    ACEPTADA = "aceptada"                # Pasajero aceptó una oferta
    CONFIRMADA = "confirmada"            # Conductor confirmó inicio
    EN_CURSO = "en_curso"                # Viaje iniciado
    COMPLETADO = "completado"            # Viaje finalizado
    CANCELADO = "cancelado"              # Cancelado por alguna parte
    
class GestorEstados:
    """Maneja las transiciones de estado"""
    
    TRANSICIONES_VALIDAS = {
        EstadoViaje.PENDIENTE: [EstadoViaje.CON_OFERTAS, EstadoViaje.CANCELADO],
        EstadoViaje.CON_OFERTAS: [EstadoViaje.ACEPTADA, EstadoViaje.CANCELADO],
        EstadoViaje.ACEPTADA: [EstadoViaje.CONFIRMADA, EstadoViaje.CANCELADO],
        EstadoViaje.CONFIRMADA: [EstadoViaje.EN_CURSO, EstadoViaje.CANCELADO],
        EstadoViaje.EN_CURSO: [EstadoViaje.COMPLETADO, EstadoViaje.CANCELADO],
        EstadoViaje.COMPLETADO: [],
        EstadoViaje.CANCELADO: []
    }
    
    @staticmethod
    def puede_transicionar(estado_actual: str, estado_nuevo: str) -> bool:
        """Verifica si una transición es válida"""
        try:
            actual = EstadoViaje(estado_actual)
            nuevo = EstadoViaje(estado_nuevo)
            return nuevo in GestorEstados.TRANSICIONES_VALIDAS[actual]
        except (ValueError, KeyError):
            return False
    
    @staticmethod
    def actualizar_estado(viaje: dict, nuevo_estado: str, 
                         usuario_id: int, motivo: str = "") -> bool:
        """
        Actualiza el estado de un viaje con validación
        """
        if not GestorEstados.puede_transicionar(
            viaje.get('estado'), nuevo_estado
        ):
            print(f"❌ Transición inválida: {viaje.get('estado')} → {nuevo_estado}")
            return False
        
        viaje['estado'] = nuevo_estado
        viaje['fecha_actualizacion'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Agregar al historial
        if 'historial_estados' not in viaje:
            viaje['historial_estados'] = []
            
        viaje['historial_estados'].append({
            'estado': nuevo_estado,
            'fecha': viaje['fecha_actualizacion'],
            'usuario_id': usuario_id,
            'motivo': motivo
        })
        
        return True

# Integración con el sistema actual
def obtener_viajes_activos_pasajero(pasajero_id: int):
    """Obtiene viajes activos de un pasajero"""
    from servicios.solicitudes_mejoradas import _leer_json, SOLICITUDES_FILE
    
    solicitudes = _leer_json(SOLICITUDES_FILE)
    
    estados_activos = [
        EstadoViaje.PENDIENTE.value,
        EstadoViaje.CON_OFERTAS.value,
        EstadoViaje.ACEPTADA.value,
        EstadoViaje.CONFIRMADA.value,
        EstadoViaje.EN_CURSO.value
    ]
    
    return [
        s for s in solicitudes 
        if s.get('pasajero_id') == pasajero_id 
        and s.get('estado') in estados_activos
    ]

def obtener_viajes_activos_conductor(conductor_id: int):
    """Obtiene viajes activos de un conductor"""
    from servicios.solicitudes_mejoradas import _leer_json, SOLICITUDES_FILE
    
    solicitudes = _leer_json(SOLICITUDES_FILE)
    
    estados_conductor = [
        EstadoViaje.CONFIRMADA.value,
        EstadoViaje.EN_CURSO.value
    ]
    
    return [
        s for s in solicitudes 
        if s.get('conductor_id') == conductor_id 
        and s.get('estado') in estados_conductor
    ]