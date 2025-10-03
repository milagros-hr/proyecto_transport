from estructuras.grafo import Grafo

def crear_grafo_lima() -> Grafo:
    g = Grafo()
    # Pesos aproximados (distancia/tiempo relativos). Ajusta a gusto para el curso.
    edges = [
        ("Cercado de Lima", "Jesús María", 3),
        ("Cercado de Lima", "Lince", 4),
        ("Lince", "San Isidro", 2),
        ("San Isidro", "Miraflores", 3),
        ("Miraflores", "Barranco", 3),
        ("Miraflores", "Surquillo", 2),
        ("Surquillo", "San Borja", 3),
        ("San Borja", "Surco", 4),
        ("Surco", "La Molina", 6),
        ("Cercado de Lima", "Pueblo Libre", 4),
        ("Pueblo Libre", "San Miguel", 3),
        ("San Miguel", "Callao", 7),
        ("Jesús María", "Lince", 2),
        ("San Isidro", "San Borja", 4),
    ]
    for u, v, w in edges:
        g.agregar_arista(u, v, w, bidireccional=True)
    return g

GRAFO = crear_grafo_lima()

def calcular_mejor_ruta(origen: str, destino: str):
    return GRAFO.dijkstra(origen, destino)  # (distancia, [nodos])
