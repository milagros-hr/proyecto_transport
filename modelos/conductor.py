from dataclasses import dataclass
from datetime import datetime
from typing import List

@dataclass
class Conductor:
    """Clase para representar a un Conductor en TransPort."""
    id: int
    nombre: str
    correo: str
    telefono: str
    
    # Campos exclusivos de Conductor, tomados del formulario de registro
    licencia: str
    placa: str
    modelo: str
    color: str
    
    # Campos base de usuario
    tipo: str = "conductor" 
    fecha_registro: str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
