class NodoCola:
    __slots__ = ("dato", "sig")
    def __init__(self, dato):
        self.dato = dato
        self.sig = None

class Cola:
    def __init__(self):
        self.frente = None
        self.final = None
        self._len = 0

    def __len__(self): return self._len
    def esta_vacia(self): return self.frente is None

    def encolar(self, dato):
        n = NodoCola(dato)
        if not self.final:
            self.frente = self.final = n
        else:
            self.final.sig = n
            self.final = n
        self._len += 1

    def desencolar(self):
        if not self.frente:
            return None
        n = self.frente
        self.frente = n.sig
        if not self.frente:
            self.final = None
        self._len -= 1
        return n.dato

    def ver_frente(self):
        return self.frente.dato if self.frente else None
