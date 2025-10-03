from dataclasses import dataclass
from datetime import datetime
from typing import List

@dataclass
class Viaje:
    id: int
    pasajero_id: int
    conductor_id: int
    origen: str
    destino: str
    ruta: List[str]
    distancia: float
    fecha: str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
