class Nodo:
    __slots__ = ("dato", "sig")
    def __init__(self, dato):
        self.dato = dato
        self.sig = None

class ListaEnlazada:
    def __init__(self):
        self.cabeza = None
        self._len = 0

    def __len__(self):
        return self._len

    def esta_vacia(self):
        return self.cabeza is None

    def insertar_final(self, dato):
        nuevo = Nodo(dato)
        if not self.cabeza:
            self.cabeza = nuevo
        else:
            p = self.cabeza
            while p.sig:
                p = p.sig
            p.sig = nuevo
        self._len += 1

    def buscar(self, predicado):
        p = self.cabeza
        while p:
            if predicado(p.dato):
                return p.dato
            p = p.sig
        return None

    def eliminar_primero(self, predicado):
        ant = None
        p = self.cabeza
        while p:
            if predicado(p.dato):
                if ant: ant.sig = p.sig
                else:   self.cabeza = p.sig
                self._len -= 1
                return p.dato
            ant, p = p, p.sig
        return None

    def recorrer(self):
        p = self.cabeza
        while p:
            yield p.dato
            p = p.sig

    def a_lista(self):
        return list(self.recorrer())
