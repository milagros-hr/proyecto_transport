import heapq

class Grafo:
    def __init__(self):
        self.adj = {}  # {u: {v: peso, ...}}

    def agregar_vertice(self, v):
        self.adj.setdefault(v, {})

    def agregar_arista(self, u, v, peso: float, bidireccional=True):
        self.agregar_vertice(u); self.agregar_vertice(v)
        self.adj[u][v] = float(peso)
        if bidireccional:
            self.adj[v][u] = float(peso)

    def vecinos(self, u):
        return self.adj.get(u, {}).items()

    def dijkstra(self, origen, destino):
        dist = {origen: 0.0}
        prev = {}
        pq = [(0.0, origen)]
        visit = set()

        while pq:
            d, u = heapq.heappop(pq)
            if u in visit: continue
            visit.add(u)

            if u == destino:
                # reconstruir camino
                path = [u]
                while u in prev:
                    u = prev[u]
                    path.append(u)
                path.reverse()
                return d, path

            for v, w in self.vecinos(u):
                nd = d + w
                if v not in dist or nd < dist[v]:
                    dist[v] = nd
                    prev[v] = u
                    heapq.heappush(pq, (nd, v))

        return float("inf"), []
