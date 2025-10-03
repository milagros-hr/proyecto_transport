from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from datetime import datetime

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

    # POST
    nombre = request.form.get("nombre", "").strip()
    correo = request.form.get("correo", "").strip()
    telefono = request.form.get("telefono", "").strip()

    tipo = (request.form.get("tipo") or request.form.get("tipo_usuario") or "").strip()

    licencia = request.form.get("licencia", "").strip() if tipo == "conductor" else None
    placa    = request.form.get("placa", "").strip() if tipo == "conductor" else None
    modelo   = request.form.get("modelo", "").strip() if tipo == "conductor" else None
    color    = request.form.get("color", "").strip() if tipo == "conductor" else None

    # Validaciones
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

    if usuario_existe(correo, tipo):
        flash(f"❌ Ya existe un {tipo} registrado con ese correo electrónico", "error")
        return render_template("registro.html")

    usuarios = get_usuarios(tipo)
    nuevo_usuario = {
        'id': generar_id(usuarios),
        'nombre': nombre,
        'correo': correo,
        'telefono': telefono,
        'tipo': tipo,
        'fecha_registro': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    if tipo == "conductor":
        nuevo_usuario.update({
            'licencia': licencia,
            'placa': placa,
            'modelo': modelo,
            'color': color
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
