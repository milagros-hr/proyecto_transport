from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from servicios import usuarios_repo, gestor_rutas

from datetime import datetime
import re
import servicios.gestor_rutas as gr
from werkzeug.security import generate_password_hash, check_password_hash
from servicios.usuarios_repo import (
    get_viajes_por_pasajero,
    actualizar_usuario
)
from servicios.solicitudes import (
    encolar_solicitud, 
    listar_solicitudes, 
    aceptar_solicitud_por_id,
    generar_solicitud_id
)




# --- NODOS DEL GRAFO (read-only) ---
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
  {"id":"los_olivos","nombre":"Los Olivos","lat":-11.957,"lng":-77.076},
  {"id":"smp","nombre":"San Martín de Porres","lat":-12.000,"lng":-77.070},
  {"id":"comas","nombre":"Comas","lat":-11.944,"lng":-77.062},
  {"id":"independencia","nombre":"Independencia","lat":-11.993,"lng":-77.053},
  {"id":"carabayllo","nombre":"Carabayllo","lat":-11.905,"lng":-77.031}
];

# === Importa TODO desde servicios y usa solo esto ===
from servicios.usuarios_repo import (
    PASAJEROS_FILE, CONDUCTORES_FILE,
    crear_directorio_data,
    get_usuarios, set_usuarios, usuario_existe,
    buscar_usuario_por_correo, buscar_usuario_por_id,  # (importado, pero ya no se usa en dashboard/perfil)
    obtener_estadisticas, generar_id, guardar_viaje,
    listar_conductores_disponibles
)

from servicios.solicitudes import encolar_solicitud
from servicios.gestor_rutas import calcular_mejor_ruta

app = Flask(__name__)
app.secret_key = 'tu_clave_secreta_aqui'  # en prod: usa variable de entorno

# ---------------- Helper local: buscar por id DENTRO del tipo ----------------
def get_user_by_id_and_tipo(user_id, tipo):
    try:
        uid = int(user_id)
    except Exception:
        return None
    for u in get_usuarios(tipo):
        if u.get("id") == uid:
            return u
    return None

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

    # === NUEVO: password ===
    password = (request.form.get("password") or "").strip()
    password2 = (request.form.get("password2") or "").strip()  # si tu form tiene confirm

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
    if not password: faltantes.append("contraseña")
    if tipo not in ["pasajero", "conductor"]:
        faltantes.append("tipo de usuario")

    if faltantes:
        flash(f"❌ Faltan los siguientes campos: {', '.join(faltantes)}", "error")
        return render_template("registro.html")

    # Si hay confirmación en tu HTML:
    if password2 and password != password2:
        flash("❌ Las contraseñas no coinciden", "error")
        return render_template("registro.html")

    if len(password) < 6:
        flash("❌ La contraseña debe tener al menos 6 caracteres", "error")
        return render_template("registro.html")

    # --- Validaciones de conductor ---
    if tipo == "conductor":
        licencia = licencia.upper()
        placa = placa.upper()
        modelo = modelo.title()
        color = color.title()

        import re as _re
        if not _re.fullmatch(r"[A-Z]{3}-\d{3}", placa):
            flash("❌ Formato de placa inválido. Usa ABC-123.", "error")
            return render_template("registro.html")

        if any(c.get("placa", "").upper() == placa for c in get_usuarios("conductor")):
            flash("❌ Esa placa ya está registrada.", "error")
            return render_template("registro.html")

    # --- Correo duplicado (por tipo) ---
    if usuario_existe(correo, tipo):
        flash(f"❌ Ya existe un {tipo} registrado con ese correo electrónico", "error")
        return render_template("registro.html")

    # --- Crear y guardar (con password_hash) ---
    usuarios = get_usuarios(tipo)
    nuevo_usuario = {
        "id": generar_id(usuarios),
        "nombre": nombre,
        "correo": correo,
        "telefono": telefono,
        "tipo": tipo,
        "fecha_registro": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "password_hash": generate_password_hash(password, method="pbkdf2:sha256", salt_length=16),
    }
    if tipo == "conductor":
        nuevo_usuario.update({
            "licencia": licencia,
            "placa": placa,
            "modelo": modelo,
            "color": color,
            # Añadir capacidad por defecto (asumimos 4 asientos en autos comunes)
            "capacidad": 4, 
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

    correo = (request.form.get("email") or "").strip().lower()
    password = (request.form.get("password") or "").strip()
    tipo = (request.form.get("tipo") or request.form.get("tipo_usuario") or "").strip()

    if not correo or not password:
        flash("❌ Correo y contraseña son obligatorios", "error")
        return render_template("login.html")

    # Buscar usuario por tipo (si tu HTML NO pide tipo, probamos en ambos)
    if tipo in ("pasajero", "conductor"):
        usuario = buscar_usuario_por_correo(correo, tipo)
    else:
        usuario = buscar_usuario_por_correo(correo, "pasajero") or \
                  buscar_usuario_por_correo(correo, "conductor")

    if not usuario:
        flash("❌ No se encontró un usuario con ese correo", "error")
        return render_template("login.html")

    pwd_hash = usuario.get("password_hash")
    if not pwd_hash:
        flash("❌ Tu cuenta no tiene contraseña establecida. Regístrate de nuevo.", "error")
        return render_template("login.html")

    if not check_password_hash(pwd_hash, password):
        flash("❌ Contraseña incorrecta", "error")
        return render_template("login.html")

    # OK → crear sesión
    session.clear()
    session.update(
        user_id=usuario["id"],
        user_name=usuario["nombre"],
        user_email=usuario["correo"],
        user_type=usuario["tipo"],
        user_phone=usuario["telefono"],
        user_date=usuario["fecha_registro"],
    )
    if request.form.get('remember'):
        session.permanent = True

    flash(f"✅ Bienvenido, {usuario['nombre']}!", "success")
    return redirect(url_for('dashboard'))




@app.route("/dashboard")
@requiere_login
def dashboard():
    # Usa el tipo guardado en sesión para evitar confusiones por IDs repetidos
    tipo = session.get('user_type', 'pasajero')
    usuario_actual = get_user_by_id_and_tipo(session['user_id'], tipo)
    if not usuario_actual:
        session.clear()
        flash("❌ Sesión inválida. Inicia sesión nuevamente.", "error")
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
    pasajero_id = session['user_id']
    historial_viajes = get_viajes_por_pasajero(pasajero_id)
    for viaje in historial_viajes:
        conductor = get_user_by_id_and_tipo(viaje.get("conductor_id"), "conductor")
        viaje["conductor_nombre"] = conductor["nombre"] if conductor else "No disponible"
    return render_template("mis-viajes.html", viajes=historial_viajes)


@app.route("/repetir-viaje")
@requiere_login
def repetir_viaje():
    origen = request.args.get('origen')
    destino = request.args.get('destino')
    if not origen or not destino:
        return redirect(url_for('mis_viajes'))
    return redirect(url_for('buscar_viaje', origen=origen, destino=destino))


@app.route("/crear-ruta")
@requiere_login
def crear_ruta():
    """Vista principal del conductor para gestionar solicitudes y viajes"""
    if session.get('user_type') != 'conductor':
        flash("❌ Solo los conductores pueden crear rutas", "error")
        return redirect(url_for('dashboard'))
    
    tipo = session['user_type']
    conductor = get_user_by_id_and_tipo(session['user_id'], tipo)
    
    if not conductor:
        session.clear()
        flash("❌ Sesión inválida", "error")
        return redirect(url_for('login'))
    
    return render_template('crear_ruta.html', conductor=conductor)






@app.route("/mis-rutas")
@requiere_login
def mis_rutas():
    if session.get('user_type') != 'conductor':
        flash("❌ Solo los conductores tienen rutas", "error")
        return redirect(url_for('dashboard'))
    return "<h1>🚗 Mis Rutas</h1><p>Funcionalidad en desarrollo...</p><a href='/dashboard'>🔙 Volver al Dashboard</a>"

@app.route("/perfil", methods=["GET", "POST"])
@requiere_login
def perfil():
    tipo = session['user_type']
    user_id = session['user_id']
    usuario = get_user_by_id_and_tipo(user_id, tipo)
    if not usuario:
        session.clear(); return redirect(url_for('login'))

    if request.method == "POST":
        nombre = request.form.get("nombre", "").strip()
        telefono = request.form.get("telefono", "").strip()
        if not nombre or not telefono:
            flash("❌ El nombre y el teléfono son obligatorios.", "error")
            return render_template("perfil.html", usuario=usuario)
        if actualizar_usuario(user_id, tipo, {"nombre": nombre, "telefono": telefono}):
            session['user_name'] = nombre
            session['user_phone'] = telefono
            flash("✅ Perfil actualizado.", "success")
            return redirect(url_for('dashboard'))
        else:
            flash("❌ Error al actualizar el perfil.", "error")

    return render_template("perfil.html", usuario=usuario)


# Credenciales del administrador (en producción usar variables de entorno)
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "123"

# Decorador para rutas de admin
def requiere_admin(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_logged_in' not in session or not session['admin_logged_in']:
            flash("❌ Debes iniciar sesión como administrador", "error")
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

# Ruta de login del admin
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "GET":
        return render_template("admin_login.html")
    
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    
    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        session['admin_logged_in'] = True
        session['admin_username'] = username
        flash("✅ Bienvenido, Administrador", "success")
        return redirect(url_for('listar_usuarios'))
    else:
        flash("❌ Credenciales incorrectas", "error")
        return render_template("admin_login.html")

# Logout del admin
@app.route("/admin/logout")
def admin_logout():
    session.pop('admin_logged_in', None)
    session.pop('admin_username', None)
    flash("👋 Sesión de administrador cerrada", "info")
    return redirect(url_for('inicio'))

# Modificar la ruta /usuarios para requerir autenticación de admin
@app.route("/usuarios")
@requiere_admin
def listar_usuarios():
    pasajeros = get_usuarios("pasajero")
    conductores = get_usuarios("conductor")
    return render_template("usuarios.html", pasajeros=pasajeros, conductores=conductores)

# Modificar la ruta /limpiar_datos para requerir autenticación de admin
def vaciar_archivo_json(path):
    try:
        print(f"Intentando vaciar: {path}")
        if not os.path.exists(path):
            print(f"⚠️ No existe el archivo: {path}")
            return False
        with open(path, "w", encoding="utf-8") as f:
            json.dump([], f, indent=4, ensure_ascii=False)
        print(f"✔️ Vacío correctamente: {path}")
        return True
    except Exception as e:
        print(f"❌ Error al vaciar {path}: {e}")
        return False


@app.route("/limpiar_datos")
@requiere_admin
def limpiar_datos():
    DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

    archivos = [
        os.path.join(DATA_DIR, "pasajeros.json"),
        os.path.join(DATA_DIR, "conductores.json"),
        os.path.join(DATA_DIR, "solicitudes.json"),
        os.path.join(DATA_DIR, "contraofertas.json"),
    ]

    resultados = [vaciar_archivo_json(path) for path in archivos]

    for path, ok in zip(archivos, resultados):
        print(f"{'✅' if ok else '❌'} {os.path.basename(path)}")

    todo_ok = all(resultados)
    flash("🗑️ Todos los datos han sido eliminados" if todo_ok else "❌ Error al limpiar los datos",
          "info" if todo_ok else "error")

    return redirect(url_for("listar_usuarios"))


# ---- Inyecta stats en todas las plantillas ----
@app.context_processor
def inject_stats():
    return {'stats': obtener_estadisticas()}

# ---------------- API ----------------
# --- BUSCAR VIAJES DISPONIBLES ---



@app.get("/api/grafo/nodos")
def api_grafo_nodos():
    try:
        nodos = []

        if hasattr(gr, "NODOS_COORDS"):
            for nid, n in gr.NODOS_COORDS.items():
                nodos.append({
                    "id": nid,
                    "nombre": n.get("nombre", nid),
                    "lat": n.get("lat"), "lng": n.get("lng")
                })
        elif hasattr(gr, "grafo") and hasattr(gr.grafo, "nodes"):
            for nid, data in gr.grafo.nodes(data=True):
                nodos.append({
                    "id": str(nid),
                    "nombre": data.get("nombre", str(nid)),
                    "lat": data.get("lat"), "lng": data.get("lng")
                })

        if not nodos:
            nodos = FALLBACK_NODES

        return jsonify(nodos), 200
    except Exception as e:
        print("Error /api/grafo/nodos:", e)
        return jsonify([]), 500

@app.post("/api/solicitar")
@requiere_login
def api_solicitar():
    """
    El pasajero crea una solicitud de viaje
    Esta queda abierta para que los conductores puedan verla y ofertar
    """
    if session.get('user_type') != 'pasajero':
        return jsonify({"error": "Solo pasajeros"}), 403
    
    try:
        data = request.get_json(force=True)
        pasajero_id = session.get("user_id")
        
        # Normalizar origen y destino
        origen_raw = data.get("origen") or {}
        destino_raw = data.get("destino") or {}
        
        origen = {
            "nombre": origen_raw.get("nombre", "Origen"),
            "lat": float(origen_raw.get("lat", -12.0464)),
            "lng": float(origen_raw.get("lng", -77.0428))
        }
        
        destino = {
            "nombre": destino_raw.get("nombre", "Destino"),
            "lat": float(destino_raw.get("lat", -12.0464)),
            "lng": float(destino_raw.get("lng", -77.0428))
        }
        
        distancia = float(data.get("distancia", 0.0))
        
        # Crear solicitud usando el nuevo sistema
        from servicios.solicitudes_mejoradas import crear_solicitud_pasajero
        solicitud = crear_solicitud_pasajero(
            pasajero_id=pasajero_id,
            origen=origen,
            destino=destino,
            distancia=distancia
        )
        
        if solicitud:
            flash(f"✅ Solicitud creada. Precio estimado: S/. {solicitud['precio_estandar']:.2f}", "success")
            return jsonify({
                "ok": True,
                "solicitud": solicitud,
                "mensaje": "Solicitud creada. Los conductores pueden verla y ofertar."
            }), 200
        else:
            return jsonify({"ok": False, "error": "No se pudo crear la solicitud"}), 500
            
    except Exception as e:
        print("❌ Error en /api/solicitar:", e)
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 500

# ============================================
# ENDPOINT: VER MIS SOLICITUDES ACTIVAS
# ============================================

@app.get("/api/pasajero/mis-solicitudes")
@requiere_login
def api_mis_solicitudes():
    """
    Obtiene las solicitudes activas del pasajero actual
    """
    if session.get('user_type') != 'pasajero':
        return jsonify({"error": "Solo pasajeros"}), 403
    
    try:
        pasajero_id = session['user_id']
        
        from servicios.solicitudes_mejoradas import _leer_json, SOLICITUDES_FILE
        solicitudes = _leer_json(SOLICITUDES_FILE)
        
        # Filtrar solicitudes del pasajero que estén pendientes
        mis_solicitudes = [
            s for s in solicitudes 
            if s.get('pasajero_id') == pasajero_id 
            and s.get('estado') == 'pendiente'
        ]
        
        return jsonify(mis_solicitudes), 200
        
    except Exception as e:
        print("❌ Error:", e)
        return jsonify({"error": str(e)}), 500



@app.get("/api/solicitudes")
@requiere_login
def api_listar_solicitudes():
    """Devuelve todas las solicitudes pendientes para que los conductores las vean"""
    if session.get('user_type') != 'conductor':
        return jsonify({"error": "Solo conductores"}), 403
    
    try:
        solicitudes = listar_solicitudes()
        
        # Enriquecer con información del pasajero
        resultado = []
        for sol in solicitudes:
            pasajero_id = sol.get('pasajero_id')
            pasajero = get_user_by_id_and_tipo(pasajero_id, 'pasajero')
            
            resultado.append({
                'id': sol.get('solicitud_id') or sol.get('viaje_id') or sol.get('id'),
                'pasajero_id': pasajero_id,
                'pasajero_nombre': pasajero.get('nombre') if pasajero else 'Desconocido',
                'pasajero_telefono': pasajero.get('telefono') if pasajero else 'N/A',
                'origen': sol.get('origen'),
                'destino': sol.get('destino'),
                'distancia': sol.get('distancia', 0),
                'precio_sugerido': sol.get('precio_sugerido'),
                'ruta': sol.get('ruta', []),
                'fecha': sol.get('fecha', '')
            })
        
        return jsonify(resultado), 200
    except Exception as e:
        print(f"❌ Error en /api/solicitudes: {e}")
        return jsonify({"error": str(e)}), 500


# Agregar estos endpoints a app.py

# ============================================
# ENDPOINTS PARA CONDUCTORES
# ============================================

@app.get("/api/conductor/solicitudes-cercanas")
@requiere_login
def api_solicitudes_cercanas_conductor():
    """
    Obtiene solicitudes activas cercanas a la ubicación del conductor
    """
    if session.get('user_type') != 'conductor':
        return jsonify({"error": "Solo conductores"}), 403
    
    try:
        lat = float(request.args.get('lat', -12.0464))
        lng = float(request.args.get('lng', -77.0428))
        radio = float(request.args.get('radio', 10))  # km
        
        from servicios.solicitudes_mejoradas import obtener_solicitudes_cercanas
        solicitudes = obtener_solicitudes_cercanas(lat, lng, radio)
        
        # Enriquecer con datos del pasajero
        from servicios.usuarios_repo import buscar_usuario_por_id
        for sol in solicitudes:
            pasajero = buscar_usuario_por_id(sol['pasajero_id'], 'pasajero')
            if pasajero:
                sol['pasajero_nombre'] = pasajero.get('nombre', 'Desconocido')
                sol['pasajero_telefono'] = pasajero.get('telefono', '')
        
        return jsonify(solicitudes), 200
        
    except Exception as e:
        print("❌ Error en solicitudes cercanas:", e)
        return jsonify({"error": str(e)}), 500


@app.post("/api/conductor/aceptar-solicitud")
@requiere_login
def api_aceptar_solicitud():
    """
    Conductor acepta una solicitud con el precio estándar
    """
    if session.get('user_type') != 'conductor':
        return jsonify({"error": "Solo conductores"}), 403
    
    try:
        data = request.get_json()
        solicitud_id = data.get('solicitud_id')
        conductor_id = session['user_id']
        
        from servicios.solicitudes_mejoradas import aceptar_solicitud_directa
        resultado = aceptar_solicitud_directa(conductor_id, solicitud_id)
        
        if resultado:
            return jsonify({"ok": True, "solicitud": resultado}), 200
        else:
            return jsonify({"error": "No se pudo aceptar la solicitud"}), 400
            
    except Exception as e:
        print("❌ Error aceptando solicitud:", e)
        return jsonify({"error": str(e)}), 500


@app.post("/api/conductor/contraoferta")
@requiere_login
def api_crear_contraoferta():
    """
    Conductor envía una contraoferta con precio diferente
    """
    if session.get('user_type') != 'conductor':
        return jsonify({"error": "Solo conductores"}), 403
    
    try:
        data = request.get_json()
        solicitud_id = data.get('solicitud_id')
        precio_ofrecido = float(data.get('precio_ofrecido', 0))
        mensaje = data.get('mensaje', '')
        conductor_id = session['user_id']
        
        if precio_ofrecido <= 0:
            return jsonify({"error": "Precio inválido"}), 400
        
        from servicios.solicitudes_mejoradas import crear_contraoferta
        resultado = crear_contraoferta(conductor_id, solicitud_id, precio_ofrecido, mensaje)
        
        if resultado:
            return jsonify({"ok": True, "contraoferta": resultado}), 200
        else:
            return jsonify({"error": "No se pudo crear la contraoferta"}), 400
            
    except Exception as e:
        print("❌ Error creando contraoferta:", e)
        return jsonify({"error": str(e)}), 500



# ============================================
# RUTA: VISTA DE CONTRAOFERTAS
# ============================================

@app.route("/contraofertas")
@requiere_login
def contraofertas():
    """
    Vista HTML para ver contraofertas (pasajero)
    """
    if session.get('user_type') != 'pasajero':
        flash("❌ Solo los pasajeros pueden ver contraofertas", "error")
        return redirect(url_for('dashboard'))
    
    return render_template('contraofertas.html')


@app.get("/api/conductor/mis-viajes")
@requiere_login
def api_mis_viajes_conductor():
    """
    Obtiene los viajes del conductor (aceptados y en curso)
    """
    if session.get('user_type') != 'conductor':
        return jsonify({"error": "Solo conductores"}), 403
    
    try:
        conductor_id = session['user_id']
        
        from servicios.solicitudes_mejoradas import _leer_json, SOLICITUDES_FILE
        solicitudes = _leer_json(SOLICITUDES_FILE)
        
        mis_viajes = [s for s in solicitudes 
                      if s.get('conductor_id') == conductor_id 
                      and s.get('estado') in ['aceptada', 'en_curso']]
        
        # Enriquecer con datos del pasajero
        from servicios.usuarios_repo import buscar_usuario_por_id
        for viaje in mis_viajes:
            pasajero = buscar_usuario_por_id(viaje['pasajero_id'], 'pasajero')
            if pasajero:
                viaje['pasajero_nombre'] = pasajero.get('nombre', 'Desconocido')
                viaje['pasajero_telefono'] = pasajero.get('telefono', '')
        
        return jsonify(mis_viajes), 200
        
    except Exception as e:
        print("❌ Error obteniendo viajes:", e)
        return jsonify({"error": str(e)}), 500


# ============================================
# ENDPOINTS PARA PASAJEROS
# ============================================


@app.get("/api/pasajero/contraofertas")
@requiere_login
def api_contraofertas_pasajero():
    """
    Pasajero ve las contraofertas recibidas para sus solicitudes
    """
    if session.get('user_type') != 'pasajero':
        return jsonify({"error": "Solo pasajeros"}), 403
    
    try:
        pasajero_id = session['user_id']
        
        from servicios.solicitudes_mejoradas import (
            _leer_json, SOLICITUDES_FILE, obtener_contraofertas_pasajero
        )
        
        # Obtener solicitudes activas del pasajero
        solicitudes = _leer_json(SOLICITUDES_FILE)
        mis_solicitudes = [s for s in solicitudes 
                          if s['pasajero_id'] == pasajero_id 
                          and s['estado'] == 'pendiente']
        
        resultado = []
        for sol in mis_solicitudes:
            contraofertas = obtener_contraofertas_pasajero(sol['id'])
            
            # Enriquecer con datos del conductor
            from servicios.usuarios_repo import buscar_usuario_por_id
            for contra in contraofertas:
                conductor = buscar_usuario_por_id(contra['conductor_id'], 'conductor')
                if conductor:
                    contra['conductor_nombre'] = conductor.get('nombre', 'Conductor')
                    contra['conductor_vehiculo'] = f"{conductor.get('modelo', 'N/D')} - {conductor.get('placa', '')}"
                    contra['conductor_calificacion'] = 4.5  # Placeholder
            
            if contraofertas:
                resultado.append({
                    "solicitud": sol,
                    "contraofertas": contraofertas
                })
        
        return jsonify(resultado), 200
        
    except Exception as e:
        print("❌ Error obteniendo contraofertas:", e)
        return jsonify({"error": str(e)}), 500


@app.post("/api/pasajero/aceptar-contraoferta")
@requiere_login
def api_aceptar_contraoferta():
    """
    Pasajero acepta una contraoferta específica
    """
    if session.get('user_type') != 'pasajero':
        return jsonify({"error": "Solo pasajeros"}), 403
    
    try:
        data = request.get_json()
        contraoferta_id = data.get('contraoferta_id')
        pasajero_id = session['user_id']
        
        from servicios.solicitudes_mejoradas import pasajero_acepta_contraoferta
        resultado = pasajero_acepta_contraoferta(pasajero_id, contraoferta_id)
        
        if resultado:
            return jsonify({"ok": True, "viaje": resultado}), 200
        else:
            return jsonify({"error": "No se pudo aceptar la contraoferta"}), 400
            
    except Exception as e:
        print("❌ Error aceptando contraoferta:", e)
        return jsonify({"error": str(e)}), 500


@app.post("/api/cancelar-solicitud")
@requiere_login
def api_cancelar_solicitud():
    """
    Cancela una solicitud (pasajero o conductor)
    """
    try:
        data = request.get_json()
        solicitud_id = data.get('solicitud_id')
        motivo = data.get('motivo', '')
        usuario_id = session['user_id']
        
        from servicios.solicitudes_mejoradas import cancelar_solicitud
        resultado = cancelar_solicitud(solicitud_id, usuario_id, motivo)
        
        if resultado:
            return jsonify({"ok": True}), 200
        else:
            return jsonify({"error": "No se pudo cancelar"}), 400
            
    except Exception as e:
        print("❌ Error cancelando:", e)
        return jsonify({"error": str(e)}), 500
    




@app.post("/api/conductor/finalizar-viaje")
@requiere_login
def api_finalizar_viaje():
    """El conductor finaliza el viaje"""
    if session.get('user_type') != 'conductor':
        return jsonify({"error": "Solo conductores"}), 403
    
    try:
        data = request.get_json(force=True)
        viaje_id = data.get('viaje_id')
        
        viajes = _leer_json(VIAJES_FILE)
        viaje_encontrado = False
        
        for viaje in viajes:
            if viaje.get('id') == viaje_id and viaje.get('conductor_id') == session['user_id']:
                if viaje.get('estado') == 'en_curso':
                    viaje['estado'] = 'completado'
                    viaje['hora_fin'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    viaje_encontrado = True
                    break
        
        if viaje_encontrado:
            _guardar_json_atomic(VIAJES_FILE, viajes)
            return jsonify({"ok": True, "mensaje": "Viaje completado"}), 200
        else:
            return jsonify({"error": "Viaje no encontrado o no está en curso"}), 404
            
    except Exception as e:
        print(f"❌ Error en /api/conductor/finalizar-viaje: {e}")
        return jsonify({"error": str(e)}), 500
    

@app.get("/api/solicitudes_cercanas")
@requiere_login
def solicitudes_cercanas():
    """Devuelve solicitudes cercanas a la ubicación del conductor"""
    try:
        lat = float(request.args.get("lat", -12.0464))
        lng = float(request.args.get("lng", -77.0428))

        # Cargar solicitudes desde archivo JSON
        from servicios.solicitudes import leer_solicitudes
        solicitudes = leer_solicitudes()

        # Filtro básico: devolver las más cercanas (simulado)
        cercanas = []
        for s in solicitudes:
            o = s.get("origen", {})
            if isinstance(o, dict) and "lat" in o and "lng" in o:
                dist = ((lat - o["lat"])**2 + (lng - o["lng"])**2)**0.5
                if dist < 0.1:  # radio de ~10 km
                    cercanas.append(s)

        return jsonify(cercanas or []), 200
    except Exception as e:
        print("Error en /api/solicitudes_cercanas:", e)
        return jsonify([]), 500

# --- Helpers de geodatos ---

def _nodos_catalog():
    # Intenta obtener nodos con coords desde servicios.gestor_rutas o usa FALLBACK_NODES
    nodos = {}
    try:
        if hasattr(gr, "NODOS_COORDS"):
            for nid, n in gr.NODOS_COORDS.items():
                nodos[str(n.get("nombre", nid)).strip().lower()] = (float(n["lat"]), float(n["lng"]))
        elif hasattr(gr, "grafo") and hasattr(gr.grafo, "nodes"):
            for nid, data in gr.grafo.nodes(data=True):
                nombre = str(data.get("nombre", nid)).strip().lower()
                if "lat" in data and "lng" in data:
                    nodos[nombre] = (float(data["lat"]), float(data["lng"]))
    except Exception:
        pass
    # Fallback a constantes
    if not nodos:
        for n in FALLBACK_NODES:
            nombre = str(n.get("nombre", n.get("id"))).strip().lower()
            nodos[nombre] = (float(n["lat"]), float(n["lng"]))
    return nodos

_NODOS_LIMA = _nodos_catalog()

def _lookup_coords(nombre):
    if not nombre:
        return None
    key = str(nombre).strip().lower()
    return _NODOS_LIMA.get(key)

def _norm_point(p):
    """Normaliza un punto {nombre, lat, lng}; si faltan coords, las busca por nombre."""
    if not isinstance(p, dict):
        p = {"nombre": str(p)}
    nombre = p.get("nombre") or p.get("texto") or p.get("id") or "Desconocido"
    lat = p.get("lat")
    lng = p.get("lng")
    if lat is None or lng is None:
        hit = _lookup_coords(nombre)
        if hit:
            lat, lng = hit
    try:
        return {
            "nombre": str(nombre),
            "lat": float(lat if lat is not None else -12.0464),
            "lng": float(lng if lng is not None else -77.0428),
        }
    except Exception:
        return {"nombre": str(nombre), "lat": -12.0464, "lng": -77.0428}



@app.get("/api/pasajero/ofertas-pendientes")
@requiere_login
def api_ofertas_pendientes():
    """El pasajero ve las ofertas que los conductores le han hecho"""
    if session.get('user_type') != 'pasajero':
        return jsonify({"error": "Solo pasajeros"}), 403
    
    try:
        pasajero_id = session['user_id']
        viajes = _leer_json(VIAJES_FILE)
        
        # Filtrar viajes pendientes de confirmación para este pasajero
        ofertas = [
            v for v in viajes 
            if v.get('pasajero_id') == pasajero_id 
            and v.get('estado') == 'pendiente_confirmacion'
        ]
        
        # Enriquecer con info del conductor
        for oferta in ofertas:
            conductor = get_user_by_id_and_tipo(oferta.get('conductor_id'), 'conductor')
            if conductor:
                oferta['conductor_nombre'] = conductor.get('nombre')
                oferta['conductor_telefono'] = conductor.get('telefono')
                oferta['conductor_vehiculo'] = f"{conductor.get('modelo')} {conductor.get('color')} - {conductor.get('placa')}"
        
        return jsonify(ofertas), 200
        
    except Exception as e:
        print(f"❌ Error en /api/pasajero/ofertas-pendientes: {e}")
        return jsonify({"error": str(e)}), 500


@app.post("/api/pasajero/confirmar-oferta")
@requiere_login
def api_confirmar_oferta():
    """El pasajero acepta la oferta de un conductor"""
    if session.get('user_type') != 'pasajero':
        return jsonify({"error": "Solo pasajeros"}), 403
    
    try:
        data = request.get_json(force=True)
        viaje_id = data.get('viaje_id')
        
        viajes = _leer_json(VIAJES_FILE)
        viaje_encontrado = False
        
        for viaje in viajes:
            if viaje.get('id') == viaje_id and viaje.get('pasajero_id') == session['user_id']:
                if viaje.get('estado') == 'pendiente_confirmacion':
                    viaje['estado'] = 'confirmado'
                    viaje['fecha_confirmacion'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    viaje_encontrado = True
                    break
        
        if viaje_encontrado:
            _guardar_json_atomic(VIAJES_FILE, viajes)
            return jsonify({
                "ok": True, 
                "mensaje": "Oferta confirmada. El conductor puede iniciar el viaje."
            }), 200
        else:
            return jsonify({"error": "Viaje no encontrado"}), 404
            
    except Exception as e:
        print(f"❌ Error en /api/pasajero/confirmar-oferta: {e}")
        return jsonify({"error": str(e)}), 500


@app.post("/api/pasajero/rechazar-oferta")
@requiere_login
def api_rechazar_oferta():
    """El pasajero rechaza la oferta de un conductor"""
    if session.get('user_type') != 'pasajero':
        return jsonify({"error": "Solo pasajeros"}), 403
    
    try:
        data = request.get_json(force=True)
        viaje_id = data.get('viaje_id')
        
        viajes = _leer_json(VIAJES_FILE)
        viaje_encontrado = False
        
        for viaje in viajes:
            if viaje.get('id') == viaje_id and viaje.get('pasajero_id') == session['user_id']:
                if viaje.get('estado') == 'pendiente_confirmacion':
                    viaje['estado'] = 'rechazado'
                    viaje['fecha_rechazo'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    viaje_encontrado = True
                    break
        
        if viaje_encontrado:
            _guardar_json_atomic(VIAJES_FILE, viajes)
            return jsonify({
                "ok": True, 
                "mensaje": "Oferta rechazada."
            }), 200
        else:
            return jsonify({"error": "Viaje no encontrado"}), 404
            
    except Exception as e:
        print(f"❌ Error en /api/pasajero/rechazar-oferta: {e}")
        return jsonify({"error": str(e)}), 500


# ============================================
# HELPER: CALCULAR DISTANCIA ENTRE COORDENADAS
# ============================================

def calcular_distancia_haversine(lat1, lng1, lat2, lng2):
    """
    Calcula la distancia en km entre dos coordenadas usando Haversine
    """
    from math import radians, sin, cos, sqrt, atan2
    
    R = 6371  # Radio de la Tierra en km
    
    dlat = radians(lat2 - lat1)
    dlon = radians(lng2 - lng1)
    
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    
    return R * c


# ============================================
# ENDPOINT: CALCULAR DISTANCIA
# ============================================

@app.post("/api/calcular-distancia")
def api_calcular_distancia():
    """
    Calcula la distancia entre dos puntos
    """
    try:
        data = request.get_json()
        
        origen = data.get('origen', {})
        destino = data.get('destino', {})
        
        lat1 = float(origen.get('lat', 0))
        lng1 = float(origen.get('lng', 0))
        lat2 = float(destino.get('lat', 0))
        lng2 = float(destino.get('lng', 0))
        
        distancia = calcular_distancia_haversine(lat1, lng1, lat2, lng2)
        
        from servicios.solicitudes_mejoradas import calcular_precio
        precio = calcular_precio(distancia)
        
        return jsonify({
            "distancia": round(distancia, 2),
            "precio_estimado": round(precio, 2),
            "tiempo_estimado": round(distancia * 3, 0)  # ~3 min por km
        }), 200
        
    except Exception as e:
        print("❌ Error calculando distancia:", e)
        return jsonify({"error": str(e)}), 500


# ============================================
# BUSCAR VIAJES - CORREGIDO
# ============================================

@app.get("/api/buscar-viajes")
def buscar_viajes():
    """
    Calcula la ruta y devuelve información al pasajero.
    Si no existe ruta, usa fallback con distancia estimada.
    """
    try:
        origen = request.args.get("origen")
        destino = request.args.get("destino")
        pasajeros = int(request.args.get("pasajeros", 1))

        if not origen or not destino:
            return jsonify({"error": "Faltan parámetros"}), 400

        # Calcular ruta en grafo
        distancia, ruta = gestor_rutas.calcular_mejor_ruta(origen, destino)

        # Fallback: si no hay ruta válida, usar una distancia genérica
        if distancia == float("inf") or not ruta:
            print(f"⚠️ Ruta no encontrada entre {origen} y {destino}. Usando estimación.")
            distancia = 5.0  # valor genérico (km)
            ruta = [origen, destino]

        # Calcular precio y tiempo
        from servicios.solicitudes_mejoradas import calcular_precio
        precio_estimado = round(calcular_precio(distancia), 2)
        tiempo_estimado = round(distancia * 3, 1)

        return jsonify({
            "ok": True,
            "distancia": distancia,
            "ruta": ruta,
            "precio_estimado": precio_estimado,
            "tiempo_estimado": tiempo_estimado,
            "mensaje": "Ruta estimada lista para solicitar"
        }), 200

    except Exception as e:
        print("❌ Error en /api/buscar-viajes:", e)
        import traceback; traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 500




# ---------------- Main ----------------
if __name__ == "__main__":
    import os

    # Inicializa directorios y archivos
    crear_directorio_data()
    print("🚖 TransPort iniciado - Datos en /data")
    print(f"📁 Pasajeros:  {PASAJEROS_FILE.resolve()}")
    print(f"📁 Conductores: {CONDUCTORES_FILE.resolve()}")

    # Ejecuta el servidor Flask
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
