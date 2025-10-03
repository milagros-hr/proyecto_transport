from dataclasses import dataclass
from datetime import datetime
from typing import List

@dataclass
class Pasajero:
    id: int
    nombre: str
    correo: str
    telefono: str
    tipo: str = "pasajero"
    fecha_registro: str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
