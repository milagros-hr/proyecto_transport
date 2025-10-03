¡hecho! Aquí tienes un **README.md** listo para pegar en tu proyecto. Explica la estructura, cómo correrlo, el flujo de “Buscar viaje”, endpoints, y cómo depurar los típicos errores 👇

---

# TransPort (Flask + Leaflet)

Mini app de taxi con registro/login, listado de usuarios y búsqueda de viajes sobre un mapa.
Persistencia simple en archivos JSON (carpeta `data/`).

## 📁 Estructura del proyecto

```
PROYECTO_TRANSPORT/
├─ app.py
├─ requirements.txt
├─ .gitignore
├─ data/
│  ├─ pasajeros.json
│  ├─ conductores.json
│  └─ viajes.json
├─ estructuras/
│  ├─ cola.py
│  ├─ grafo.py
│  └─ lista_enlazada.py
├─ modelos/
│  ├─ conductor.py
│  ├─ pasajero.py
│  └─ viaje.py
├─ servicios/
│  ├─ gestor_rutas.py
│  ├─ solicitudes.py
│  └─ usuarios_repo.py
├─ static/
│  ├─ taxi-lima.png
│  └─ js/
│     └─ buscar_viaje.js
└─ templates/
   ├─ index.html
   ├─ login.html
   ├─ registro.html
   ├─ dashboard.html
   ├─ buscar_viaje.html
   └─ usuarios.html
```

---

## 🚀 Arranque rápido

1. **Crear venv e instalar dependencias**

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
```

2. **Ejecutar la app**

```bash
python app.py
# o con Flask
# set FLASK_APP=app.py   (Windows)   | export FLASK_APP=app.py (macOS/Linux)
# flask run --debug
```

3. **Abrir en el navegador:**
   `http://127.0.0.1:5000/`

---

## 🔐 Variables útiles (opcional)

* En `app.py`: `app.secret_key = 'tu_clave_secreta_aqui'`
  En producción, usa variable de entorno:

  ```bash
  set SECRET_KEY=algo_super_secreto   # Windows
  export SECRET_KEY=algo_super_secreto # macOS/Linux
  ```

---

## 🧭 Flujo de la app

### 1) Registro / Login

* **/registro**: crea **pasajero** o **conductor** (si es conductor, requiere licencia/placa/modelo/color).
* **/login**: inicia sesión por correo (busca en pasajeros y/o conductores).

Los datos se guardan en `data/pasajeros.json` y `data/conductores.json`.
**Verificación rápida:** abre **/usuarios** y confirma que aparezcan.

### 2) Dashboard

* Te muestra stats y accesos rápidos.

### 3) Buscar viaje (mapa)

* **/buscar-viaje**:

  * Mapa Leaflet centrado en Lima.
  * Puedes: **clickear en el mapa** o **escribir** un nodo para **Origen/Destino**.
  * Botón “mi ubicación” hace geolocalización y **snap** al nodo más cercano.
  * Botón **Buscar** llama a `/api/buscar-viajes`, traza la ruta y lista conductores.
  * “Seleccionar viaje” hace `POST /api/solicitar` y guarda en `data/viajes.json`.

> Si todavía no expones tus nodos por backend, el frontend usa **FALLBACK_NODES** (Miraflores, Barranco, etc.) para que el mapa **siempre** tenga puntos.

---

## 🔌 Endpoints principales

### Web (HTML)

* `GET /` → Landing
* `GET|POST /registro`
* `GET|POST /login`
* `GET /dashboard` (requiere login)
* `GET /usuarios` (debug/listado)

### API (usadas por el mapa)

* `GET /api/buscar-viajes?origen=...&destino=...&pasajeros=...`
  Respuesta ejemplo:

  ```json
  {
    "distancia": 8.4,
    "ruta": ["Centro de Lima", "Miraflores", "Barranco"], 
    "resultados": [
      {
        "id": 12,
        "conductor": "Ana",
        "vehiculo": "Corolla - ABC-123",
        "precio": "S/ 10.20",
        "tiempo": "22 min",
        "origen": "Centro de Lima",
        "destino": "Barranco",
        "asientos": 4
      }
    ]
  }
  ```
* `POST /api/solicitar`
  Body:

  ```json
  {
    "conductor_id": 12,
    "origen": "Centro de Lima",
    "destino": "Barranco",
    "ruta": [],
    "distancia": 0
  }
  ```

  Respuesta:

  ```json
  {"ok": true, "viaje": { "id": 99, "pasajero_id": 1, "conductor_id": 12, ... }}
  ```

### (Opcional) Nodos del grafo

* `GET /api/grafo/nodos`
  Respuesta:

  ```json
  [
    {"id":"miraflores","nombre":"Miraflores","lat":-12.1203,"lng":-77.0282},
    {"id":"barranco","nombre":"Barranco","lat":-12.1406,"lng":-77.0214}
  ]
  ```

> Si no implementas este endpoint, **no pasa nada**: el JS usa `FALLBACK_NODES`.

---

## 🗺️ Cómo funciona el mapa

* **Leaflet** + **OpenStreetMap** para tiles.
* Click en el mapa → toma lat/lng → **snap al nodo** más cercano (Haversine).
* “Mi ubicación” (geolocalización web) → también hace snap a nodo.
* Inputs `Origen/Destino` tienen **datalist** (`nodosList`) con autocompletado.
* Se hace **reverse geocoding** (Nominatim) para mostrar texto humano (avenida, zona).

  > Puede no ser 100% exacta, pero **el conductor usa el pin exacto** (coordenadas) para ubicarse.


---

## 🧪 Prueba guiada (2 minutos)

1. Abre `/registro` y crea:

   * un **pasajero** (para loguearte),
   * y un **conductor** (con placa/modelo/color/licencia).
2. Haz **login** como pasajero.
3. Entra a **/buscar-viaje**:

   * Pulsa **“mi ubicación”** → debe marcar “Origen” (snap al nodo).
   * Haz click en el mapa cerca del destino → se llena “Destino”.
   * Pulsa **Buscar** → aparece la **ruta** y conductores.
   * Pulsa **Seleccionar viaje** → se guarda en `data/viajes.json`.

---

## 🛠️ Problemas comunes & soluciones

**1) No veo puntos en el mapa**

* Ver consola del navegador:

  * Si ves `404 /static/js/buscar_viaje.js?v=1`, revisa la ruta y el nombre del archivo.
  * Limpia caché cambiando el `?v=1` a `?v=2`.
* Aunque falle `/api/grafo/nodos`, con **FALLBACK_NODES** deberías ver puntos.

**2) Geolocalización no funciona**

* Navegador puede pedir permiso.
* En `http://localhost` suele estar permitido; en otros orígenes, puede requerir HTTPS.

**3) No me registra conductores**

* El form **debe** enviar `tipo_usuario=conductor` y los campos: `licencia`, `placa`, `modelo`, `color`.
* Tu ruta `/registro` valida esos campos si `tipo == "conductor"`.

**4) “Dirección” no es exacta**

* Es normal en Nominatim. La app usa el **pin** exacto para la ubicación; el texto es solo informativo.

---

## 🧩 Extensiones futuras

* Hacer **persistencia** real de rutas/nodos desde `gestor_rutas.grafo`.
* Añadir **/mis-viajes** con listado real desde `data/viajes.json`.
* Usar **HTTPS** y clave de API para un geocoder más preciso (si migras a un servicio externo).

---
