from estructuras.grafo import Grafo

def crear_grafo_lima() -> Grafo:
    g = Grafo()
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

        ("Los Olivos", "San Martín de Porres", 3),
        ("San Martín de Porres", "Independencia", 3),
        ("San Martín de Porres", "Comas", 4),
        ("Comas", "Carabayllo", 5),
        ("Independencia", "Jesús María", 6),
        ("San Martín de Porres", "Cercado de Lima", 7)
    ]

    for u, v, w in edges:
        g.agregar_arista(u, v, w, bidireccional=True)
    return g


GRAFO = crear_grafo_lima()

def calcular_mejor_ruta(origen: str, destino: str):
    return GRAFO.dijkstra(origen, destino)  # (distancia, [nodos])
