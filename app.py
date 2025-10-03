from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from datetime import datetime
import re
from flask import jsonify
import servicios.gestor_rutas as gr

# --- NODOS DEL GRAFO (read-only) ---
from flask import jsonify
import servicios.gestor_rutas as gr  # importa tu gestor real

# Fallback con los mismos nodos que dibujabas antes (si tu grafo aún no trae coords)
FALLBACK_NODES = [
    {"id":"centro_lima","nombre":"Centro de Lima","lat":-12.0464,"lng":-77.0428},
    {"id":"miraflores","nombre":"Miraflores","lat":-12.1203,"lng":-77.0282},
    {"id":"san_isidro","nombre":"San Isidro","lat":-12.1040,"lng":-77.0348},
    {"id":"barranco","nombre":"Barranco","lat":-12.1406,"lng":-77.0214},
    {"id":"surco","nombre":"Surco","lat":-12.1339,"lng":-76.9931},
    {"id":"la_molina","nombre":"La Molina","lat":-12.0794,"lng":-76.9397},
    {"id":"callao","nombre":"Callao","lat":-12.0566,"lng":-77.1181},
    {"id":"san_miguel","nombre":"San Miguel","lat":-12.0773,"lng":-77.0907},
    {"id":"pueblo_libre","nombre":"Pueblo Libre","lat":-12.0740,"lng":-77.0615},
    {"id":"jesus_maria","nombre":"Jesús María","lat":-12.0719,"lng":-77.0431},
    {"id":"lince","nombre":"Lince","lat":-12.0876,"lng":-77.0364},
    {"id":"san_borja","nombre":"San Borja","lat":-12.1086,"lng":-77.0023},
    {"id":"surquillo","nombre":"Surquillo","lat":-12.1142,"lng":-77.0177},
    {"id":"cercado","nombre":"Cercado de Lima","lat":-12.0464,"lng":-77.0428},
]


# === Importa TODO desde servicios y usa solo esto ===
from servicios.usuarios_repo import (
    PASAJEROS_FILE, CONDUCTORES_FILE,  # solo para prints opcionales
    crear_directorio_data,
    get_usuarios, set_usuarios, usuario_existe,
    buscar_usuario_por_correo, buscar_usuario_por_id,
    obtener_estadisticas, generar_id, guardar_viaje,
    listar_conductores_disponibles
)
from servicios.solicitudes import encolar_solicitud, siguiente_solicitud
from servicios.gestor_rutas import calcular_mejor_ruta

app = Flask(__name__)
app.secret_key = 'tu_clave_secreta_aqui'  # en prod: usa variable de entorno

# ---------------- Decorador de auth ----------------
def requiere_login(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("❌ Debes iniciar sesión primero", "warning")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ---------------- Rutas web ----------------
@app.route("/")
def inicio():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template("index.html")

@app.route("/registro", methods=["GET", "POST"])
def registro():
    if request.method == "GET":
        return render_template("registro.html")

    # --- Campos base ---
    nombre = request.form.get("nombre", "").strip()
    apellido = request.form.get("apellido", "").strip()
    if apellido:
        nombre = f"{nombre} {apellido}".strip()

    correo = (request.form.get("correo", "") or "").strip().lower()
    telefono = request.form.get("telefono", "").strip()
    tipo = (request.form.get("tipo") or request.form.get("tipo_usuario") or "").strip()

    # --- Campos de conductor (si aplica) ---
    licencia = request.form.get("licencia", "").strip() if tipo == "conductor" else None
    placa    = request.form.get("placa", "").strip() if tipo == "conductor" else None
    modelo   = request.form.get("modelo", "").strip() if tipo == "conductor" else None
    color    = request.form.get("color", "").strip() if tipo == "conductor" else None

    # --- Validaciones de presencia ---
    faltantes = []
    if not nombre:   faltantes.append("nombre")
    if not correo:   faltantes.append("correo")
    if not telefono: faltantes.append("telefono")
    if tipo not in ["pasajero", "conductor"]:
        faltantes.append("tipo de usuario")

    if tipo == "conductor":
        if not licencia: faltantes.append("licencia")
        if not placa:    faltantes.append("placa")
        if not modelo:   faltantes.append("modelo")
        if not color:    faltantes.append("color")

    if faltantes:
        flash(f"❌ Faltan los siguientes campos: {', '.join(faltantes)}", "error")
        return render_template("registro.html")

    # --- Normaliza + valida campos de conductor ---
    if tipo == "conductor":
        licencia = licencia.upper()
        placa = placa.upper()
        modelo = modelo.title()
        color = color.title()

        # Formato de placa (ajústalo si usas otro formato)
        if not re.fullmatch(r"[A-Z]{3}-\d{3}", placa):
            flash("❌ Formato de placa inválido. Usa ABC-123.", "error")
            return render_template("registro.html")

        # Placa duplicada
        if any(c.get("placa", "").upper() == placa for c in get_usuarios("conductor")):
            flash("❌ Esa placa ya está registrada.", "error")
            return render_template("registro.html")

    # --- Correo duplicado (por tipo) ---
    if usuario_existe(correo, tipo):
        flash(f"❌ Ya existe un {tipo} registrado con ese correo electrónico", "error")
        return render_template("registro.html")

    # --- Crear y guardar ---
    usuarios = get_usuarios(tipo)
    nuevo_usuario = {
        "id": generar_id(usuarios),
        "nombre": nombre,
        "correo": correo,
        "telefono": telefono,
        "tipo": tipo,
        "fecha_registro": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    if tipo == "conductor":
        nuevo_usuario.update({
            "licencia": licencia,
            "placa": placa,
            "modelo": modelo,
            "color": color,
        })

    usuarios.append(nuevo_usuario)
    if set_usuarios(tipo, usuarios):
        flash(f"✅ {tipo.capitalize()} registrado exitosamente", "success")
        return redirect(url_for("login"))

    flash("❌ Error al guardar los datos. Inténtalo de nuevo.", "error")
    return render_template("registro.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")

    correo = (request.form.get("email") or "").strip()
    tipo = (request.form.get("tipo") or request.form.get("tipo_usuario") or "").strip()

    if not correo:
        flash("❌ El correo electrónico es obligatorio", "error")
        return render_template("login.html")

    usuario = None
    if tipo in ['pasajero', 'conductor']:
        usuario = buscar_usuario_por_correo(correo, tipo)
    else:
        usuario = buscar_usuario_por_correo(correo, 'pasajero') or \
                  buscar_usuario_por_correo(correo, 'conductor')

    if not usuario:
        flash("❌ No se encontró un usuario registrado con ese correo", "error")
        return render_template("login.html")

    session.clear()
    session.update(
        user_id=usuario['id'],
        user_name=usuario['nombre'],
        user_email=usuario['correo'],
        user_type=usuario['tipo'],
        user_phone=usuario['telefono'],
        user_date=usuario['fecha_registro'],
    )
    if request.form.get('remember'):
        session.permanent = True

    flash(f"✅ Bienvenido, {usuario['nombre']}!", "success")
    return redirect(url_for('dashboard'))

@app.route("/dashboard")
@requiere_login
def dashboard():
    usuario_actual = buscar_usuario_por_id(session['user_id'])
    if not usuario_actual:
        session.clear()
        flash("❌ Error: Usuario no encontrado", "error")
        return redirect(url_for('login'))
    stats = obtener_estadisticas()
    return render_template("dashboard.html", usuario=usuario_actual, stats=stats)

@app.route("/logout")
def logout():
    user_name = session.get('user_name', 'Usuario')
    session.clear()
    flash(f"👋 ¡Hasta luego, {user_name}!", "info")
    return redirect(url_for('inicio'))

@app.route("/buscar-viaje")
@requiere_login
def buscar_viaje():
    if session.get('user_type') != 'pasajero':
        flash("❌ Solo los pasajeros pueden buscar viajes", "error")
        return redirect(url_for('dashboard'))
    return render_template('buscar_viaje.html')

@app.route("/mis-viajes")
@requiere_login
def mis_viajes():
    if session.get('user_type') != 'pasajero':
        flash("❌ Solo los pasajeros tienen historial de viajes", "error")
        return redirect(url_for('dashboard'))
    return "<h1>📜 Mis Viajes</h1><p>Funcionalidad en desarrollo...</p><a href='/dashboard'>🔙 Volver al Dashboard</a>"

@app.route("/crear-ruta")
@requiere_login
def crear_ruta():
    if session.get('user_type') != 'conductor':
        flash("❌ Solo los conductores pueden crear rutas", "error")
        return redirect(url_for('dashboard'))
    return "<h1>🛣️ Crear Ruta</h1><p>Funcionalidad en desarrollo...</p><a href='/dashboard'>🔙 Volver al Dashboard</a>"

@app.route("/mis-rutas")
@requiere_login
def mis_rutas():
    if session.get('user_type') != 'conductor':
        flash("❌ Solo los conductores tienen rutas", "error")
        return redirect(url_for('dashboard'))
    return "<h1>🚗 Mis Rutas</h1><p>Funcionalidad en desarrollo...</p><a href='/dashboard'>🔙 Volver al Dashboard</a>"

@app.route("/perfil")
@requiere_login
def perfil():
    usuario = buscar_usuario_por_id(session['user_id'])
    return f"""
    <h1>👤 Perfil de {usuario['nombre']}</h1>
    <p><strong>📧 Email:</strong> {usuario['correo']}</p>
    <p><strong>📱 Teléfono:</strong> {usuario['telefono']}</p>
    <p><strong>🏷️ Tipo:</strong> {usuario['tipo'].title()}</p>
    <p><strong>📅 Fecha de registro:</strong> {usuario['fecha_registro']}</p>
    <p><a href='/dashboard'>🔙 Volver al Dashboard</a></p>
    """

@app.route("/usuarios")
def listar_usuarios():
    pasajeros = get_usuarios("pasajero")
    conductores = get_usuarios("conductor")
    return render_template("usuarios.html", pasajeros=pasajeros, conductores=conductores)

@app.route("/limpiar_datos")
def limpiar_datos():
    ok1 = set_usuarios("pasajero", [])
    ok2 = set_usuarios("conductor", [])
    flash("🗑️ Todos los datos han sido eliminados" if (ok1 and ok2) else "❌ Error al limpiar los datos",
          "info" if (ok1 and ok2) else "error")
    return redirect(url_for("inicio"))

# ---- Inyecta stats en todas las plantillas ----
@app.context_processor
def inject_stats():
    return {'stats': obtener_estadisticas()}

# ---------------- API ----------------
@app.get("/api/buscar-viajes")
@requiere_login
def api_buscar_viajes():
    origen = request.args.get("origen")
    destino = request.args.get("destino")
    pasajeros = int(request.args.get("pasajeros", "1"))

    if not origen or not destino:
        return jsonify({"error": "Origen y destino son obligatorios"}), 400

    distancia, ruta = calcular_mejor_ruta(origen, destino)
    if not ruta:
        return jsonify({"resultados": []})

    conductores = listar_conductores_disponibles()[:3]
    resultados = []
    for c in conductores:
        resultados.append({
            "id": c["id"],
            "conductor": c["nombre"],
            "vehiculo": f'{c.get("modelo","N/A")} - {c.get("placa","")}',
            "precio": f"S/ {max(6.0, 1.2*distancia):.2f}",
            "tiempo": f"{int(5 + distancia*2)} min",
            "origen": origen,
            "destino": destino,
            "ruta": ruta,
            "asientos": 4,
        })
    return jsonify({"distancia": distancia, "ruta": ruta, "resultados": resultados})

@app.get("/api/grafo/nodos")
def api_grafo_nodos():
    try:
        nodos = []

        # Opción A: si tu gestor expone un dict con coords
        if hasattr(gr, "NODOS_COORDS"):
            for nid, n in gr.NODOS_COORDS.items():
                nodos.append({
                    "id": nid,
                    "nombre": n.get("nombre", nid),
                    "lat": n.get("lat"), "lng": n.get("lng")
                })

        # Opción B: si tu gestor tiene .grafo tipo networkx con atributos
        elif hasattr(gr, "grafo") and hasattr(gr.grafo, "nodes"):
            for nid, data in gr.grafo.nodes(data=True):
                nodos.append({
                    "id": str(nid),
                    "nombre": data.get("nombre", str(nid)),
                    "lat": data.get("lat"), "lng": data.get("lng")
                })

        # Fallback si aún no tienes coords en el grafo
        if not nodos:
            nodos = FALLBACK_NODES

        return jsonify(nodos), 200
    except Exception as e:
        print("Error /api/grafo/nodos:", e)
        return jsonify([]), 500


@app.post("/api/solicitar")
@requiere_login
def api_solicitar():
    data = request.get_json(force=True)
    pasajero_id = session.get("user_id")
    if not pasajero_id:
        return jsonify({"error": "No autenticado"}), 401

    solicitud = {
        "pasajero_id": pasajero_id,
        "conductor_id": data.get("conductor_id"),
        "origen": data.get("origen"),
        "destino": data.get("destino"),
        "ruta": data.get("ruta", []),
        "distancia": data.get("distancia", 0.0),
    }
    encolar_solicitud(solicitud)
    s = siguiente_solicitud()
    viaje = {"id": generar_id([]), **s}
    guardar_viaje(viaje)
    return jsonify({"ok": True, "viaje": viaje})

# ---------------- Main ----------------
if __name__ == "__main__":
    crear_directorio_data()
    print("🚖 TransPort iniciado - Datos en /data")
    print(f"📁 Pasajeros:  {PASAJEROS_FILE.resolve()}")
    print(f"📁 Conductores:{CONDUCTORES_FILE.resolve()}")
    app.run(debug=True)
