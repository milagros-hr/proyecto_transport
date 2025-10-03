from estructuras.cola import Cola

# Cola global del módulo (simple para la demo)
cola_solicitudes = Cola()

def encolar_solicitud(solicitud: dict):
    cola_solicitudes.encolar(solicitud)

def siguiente_solicitud():
    return cola_solicitudes.desencolar()

def solicitudes_pendientes():
    return len(cola_solicitudes)
