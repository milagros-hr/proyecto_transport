from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from servicios import usuarios_repo, gestor_rutas
import os
import json
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
    tipo = session.get('user_type', 'pasajero')
    usuario_actual = get_user_by_id_and_tipo(session['user_id'], tipo)
    if not usuario_actual:
        session.clear()
        flash("❌ Sesión inválida. Inicia sesión nuevamente.", "error")
        return redirect(url_for('login'))
    
    stats = obtener_estadisticas()
    conteo_ofertas = 0
    conteo_viajes_pendientes = 0
    
    if tipo == 'pasajero':
        from servicios.solicitudes_mejoradas import contar_contraofertas_pendientes_pasajero
        conteo_ofertas = contar_contraofertas_pendientes_pasajero(session['user_id'])
    
    if tipo == 'conductor':
        from servicios.solicitudes_mejoradas import obtener_viajes_conductor
        viajes = obtener_viajes_conductor(session['user_id'])
        conteo_viajes_pendientes = len([v for v in viajes if v.get('estado') in ['confirmado', 'en_curso']])
    
    return render_template(
        "dashboard.html",
        usuario=usuario_actual,
        stats=stats,
        conteo_ofertas=conteo_ofertas,
        conteo_viajes_pendientes=conteo_viajes_pendientes
    )
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

# En app.py

@app.route("/mis-viajes")
@requiere_login
def mis_viajes():
    if session.get('user_type') != 'pasajero':
        flash("❌ Solo los pasajeros pueden ver su viaje", "error")
        return redirect(url_for('dashboard'))

    pasajero_id = session['user_id']

    # ✅ Leer solicitudes (viajes) del sistema mejorado
    from servicios.solicitudes_mejoradas import _leer_json, SOLICITUDES_FILE
    solicitudes = _leer_json(SOLICITUDES_FILE)

    # ✅ Estados que consideraremos "viaje activo / en proceso"
    activos = [s for s in solicitudes
               if s.get('pasajero_id') == pasajero_id
               and s.get('estado') in ['aceptada', 'confirmado', 'en_curso']]

    # Si no hay viaje activo, mostramos vacío
    if not activos:
        return render_template("mis-viajes.html", viajes=[])

    # ✅ Elegir el más reciente (por fecha_actualizacion o fecha_creacion)
    def _key_fecha(s):
        return s.get("fecha_actualizacion") or s.get("fecha_creacion") or ""

    activos.sort(key=_key_fecha, reverse=True)
    viaje = activos[0]

    # ✅ Normalizar campo "fecha" para que tu HTML actual no reviente
    viaje["fecha"] = viaje.get("fecha_creacion") or viaje.get("fecha_actualizacion") or ""

    # ✅ Enriquecer con datos del conductor (lo que tú querías)
    conductor = get_user_by_id_and_tipo(viaje.get("conductor_id"), "conductor")
    if conductor:
        viaje["conductor_nombre"] = conductor.get("nombre", "Conductor")
        viaje["conductor_telefono"] = conductor.get("telefono", "No disponible")
        viaje["conductor_placa"] = conductor.get("placa", "---")
        viaje["conductor_modelo"] = conductor.get("modelo", "Auto")
        viaje["conductor_color"] = conductor.get("color", "")

        # opcional: teléfono limpio para WA / tel:
        import re
        tel = re.sub(r"\D+", "", str(viaje["conductor_telefono"]))
        viaje["conductor_telefono_clean"] = tel
    else:
        viaje["conductor_nombre"] = "Aún sin conductor"
        viaje["conductor_telefono"] = ""
        viaje["conductor_placa"] = ""
        viaje["conductor_modelo"] = ""
        viaje["conductor_color"] = ""
        viaje["conductor_telefono_clean"] = ""

    # ✅ Le pasamos una lista con 1 solo viaje (para no tocar tu template mucho)
    return render_template("mis-viajes.html", viajes=[viaje])



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


@app.route("/historial")
@requiere_login
def historial_pasajero():
    """Historial de viajes completados del pasajero (usa ListaEnlazada)"""
    if session.get('user_type') != 'pasajero':
        flash("❌ Solo los pasajeros pueden ver su historial", "error")
        return redirect(url_for('dashboard'))
    
    from servicios.historial import (
        obtener_historial_pasajero,
        contar_viajes_completados,
        calcular_total_gastado,
        calcular_distancia_total
    )
    
    pasajero_id = session['user_id']
    historial = obtener_historial_pasajero(pasajero_id)
    
    stats = {
        'total_viajes': contar_viajes_completados(historial),
        'total_gastado': calcular_total_gastado(historial),
        'distancia_total': calcular_distancia_total(historial)
    }
    
    return render_template(
        'historial.html',
        viajes=historial.a_lista(),
        stats=stats
    )


@app.route("/historial-conductor")
@requiere_login
def historial_conductor():
    """Historial de viajes completados del conductor (usa ListaEnlazada)"""
    if session.get('user_type') != 'conductor':
        flash("❌ Solo los conductores pueden ver su historial", "error")
        return redirect(url_for('dashboard'))
    
    from servicios.historial import (
        obtener_historial_conductor,
        contar_viajes_completados,
        calcular_total_gastado,
        calcular_distancia_total
    )
    
    conductor_id = session['user_id']
    historial = obtener_historial_conductor(conductor_id)
    
    stats = {
        'total_viajes': contar_viajes_completados(historial),
        'total_ganado': calcular_total_gastado(historial),
        'distancia_total': calcular_distancia_total(historial)
    }
    
    return render_template(
        'historial-conductor.html',
        viajes=historial.a_lista(),
        stats=stats
    )

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
    Esta queda abierta para que los conductores la vean y ofertar
    """
    if session.get('user_type') != 'pasajero':
        return jsonify({"error": "Solo pasajeros"}), 403
    
    try:
        import json
        data = request.get_json(force=True)
        pasajero_id = session.get("user_id")
        
        # Raw origen/destino recibidos desde el frontend (pueden ser dict o JSON-string)
        origen_raw = data.get("origen") or {}
        destino_raw = data.get("destino") or {}
        hora_viaje = data.get("hora_viaje", "ahora")


        # Parsear si vienen como JSON-string
        try:
            if isinstance(origen_raw, str) and origen_raw.strip().startswith("{"):
                origen_raw = json.loads(origen_raw)
        except Exception:
            pass
        try:
            if isinstance(destino_raw, str) and destino_raw.strip().startswith("{"):
                destino_raw = json.loads(destino_raw)
        except Exception:
            pass
        
        # Normalizar puntos (usa helper _norm_point definido en este archivo)
        origen = _norm_point(origen_raw if isinstance(origen_raw, dict) else {"nombre": origen_raw})
        destino = _norm_point(destino_raw if isinstance(destino_raw, dict) else {"nombre": destino_raw})
        
        # Tomar distancia enviada; si no existe o es cero, recalcular con Haversine
        try:
            distancia = float(data.get("distancia", 0.0) or 0.0)
        except Exception:
            distancia = 0.0

        if distancia <= 0.0 and origen and destino:
            distancia = calcular_distancia_haversine(
                origen["lat"], origen["lng"],
                destino["lat"], destino["lng"]
            )
        
        # Crear solicitud usando el sistema mejorado
        from servicios.solicitudes_mejoradas import crear_solicitud_pasajero
        solicitud = crear_solicitud_pasajero(
            pasajero_id=pasajero_id,
            origen=origen,
            destino=destino,
            distancia=distancia,
            hora_viaje = hora_viaje
        )
        
        if solicitud:
            flash(f"✅ Solicitud creada. Precio estimado: S/. {solicitud.get('precio_estandar', 0):.2f}", "success")
            return jsonify({
                "ok": True,
                "solicitud": solicitud,
                "mensaje": "Solicitud creada. Los conductores pueden verla y ofertar."
            }), 200
        else:
            return jsonify({"ok": False, "error": "No se pudo crear la solicitud"}), 500
            
    except Exception as e:
        print("❌ Error en /api/solicitar:", e)
        import traceback; traceback.print_exc()
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
        
        # ✅ Filtrar solicitudes del pasajero en estados activos
        estados_activos = ['pendiente', 'aceptada', 'confirmado', 'en_curso']
        mis_solicitudes = [
            s for s in solicitudes 
            if s.get('pasajero_id') == pasajero_id 
            and s.get('estado') in estados_activos
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
    Pasajero ve las contraofertas recibidas Y las aceptaciones directas
    """
    if session.get('user_type') != 'pasajero':
        return jsonify({"error": "Solo pasajeros"}), 403
    
    try:
        pasajero_id = session['user_id']
        
        from servicios.solicitudes_mejoradas import obtener_ofertas_completas_pasajero
        resultado = obtener_ofertas_completas_pasajero(pasajero_id)
        
        return jsonify(resultado), 200
        
    except Exception as e:
        print("❌ Error obteniendo contraofertas:", e)
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
@app.post("/api/pasajero/confirmar-viaje-directo")
@requiere_login
def api_confirmar_viaje_directo():
    """
    Pasajero confirma un viaje que fue aceptado directamente por el conductor
    """
    if session.get('user_type') != 'pasajero':
        return jsonify({"error": "Solo pasajeros"}), 403
    
    try:
        data = request.get_json()
        solicitud_id = data.get('solicitud_id')
        pasajero_id = session['user_id']
        
        from servicios.solicitudes_mejoradas import _leer_json, SOLICITUDES_FILE, _guardar_json_atomic
        solicitudes = _leer_json(SOLICITUDES_FILE)
        
        for sol in solicitudes:
            if sol.get('id') == solicitud_id and sol.get('pasajero_id') == pasajero_id:
                if sol.get('estado') == 'aceptada':
                    sol['estado'] = 'confirmado'
                    sol['fecha_confirmacion_pasajero'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    
                    _guardar_json_atomic(SOLICITUDES_FILE, solicitudes)
                    
                    return jsonify({
                        "ok": True,
                        "mensaje": "Viaje confirmado. El conductor puede iniciar el recorrido."
                    }), 200
        
        return jsonify({"error": "Viaje no encontrado o ya confirmado"}), 404
        
    except Exception as e:
        print(f"❌ Error: {e}")
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
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.post("/api/pasajero/rechazar-contraoferta")
@requiere_login
def api_rechazar_contraoferta_pasajero():
    """
    Pasajero rechaza una contraoferta específica
    """
    if session.get('user_type') != 'pasajero':
        return jsonify({"error": "Solo pasajeros"}), 403

    try:
        data = request.get_json()
        contraoferta_id = data.get('contraoferta_id')
        pasajero_id = session['user_id']

        # Importar la nueva función
        from servicios.solicitudes_mejoradas import pasajero_rechaza_contraoferta
        resultado = pasajero_rechaza_contraoferta(pasajero_id, contraoferta_id)

        if resultado:
            return jsonify({"ok": True, "mensaje": "Oferta rechazada"}), 200
        else:
            return jsonify({"error": "No se pudo rechazar la contraoferta"}), 400

    except Exception as e:
        print("❌ Error rechazando contraoferta:", e)
        return jsonify({"error": str(e)}), 500
    


@app.post("/api/pasajero/cancelar-solicitud")
@requiere_login
def api_cancelar_solicitud_pasajero_alias():
    return api_cancelar_viaje_pasajero()


@app.post("/api/pasajero/cancelar-viaje")
@requiere_login
def api_cancelar_viaje_pasajero():
    if session.get('user_type') != 'pasajero':
        return jsonify({"ok": False, "error": "Solo pasajeros"}), 403

    try:
        data = request.get_json() or {}
        solicitud_id = data.get("solicitud_id")
        motivo = data.get("motivo", "Cancelado por el pasajero")
        pasajero_id = session["user_id"]

        if not solicitud_id:
            return jsonify({"ok": False, "error": "Falta solicitud_id"}), 400

        from servicios.solicitudes_mejoradas import cancelar_solicitud_detalle
        ok, payload = cancelar_solicitud_detalle(solicitud_id, pasajero_id, motivo)

        if ok:
            return jsonify({"ok": True, "viaje": payload}), 200
        return jsonify({"ok": False, "error": payload}), 400

    except Exception as e:
        print("❌ Error cancelando viaje:", e)
        import traceback; traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 500



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
        from servicios.solicitudes_mejoradas import _leer_json, VIAJES_FILE
        viajes = _leer_json(VIAJES_FILE)
        
        ofertas = [
            v for v in viajes 
            if v.get('pasajero_id') == pasajero_id 
            and v.get('estado') == 'pendiente_confirmacion'
        ]
        
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
        
        from servicios.solicitudes_mejoradas import _leer_json, VIAJES_FILE, _guardar_json_atomic
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
        
        from servicios.solicitudes_mejoradas import _leer_json, VIAJES_FILE, _guardar_json_atomic
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
    PRIORIDAD:
    1. Grafo (Ruta exacta por nodos conocidos).
    2. Haversine (Distancia lineal real basada en GPS).
    3. Fallback (5.0 km solo si todo lo anterior falla).
    """
    try:
        import json
        origen_arg = request.args.get("origen")
        destino_arg = request.args.get("destino")
        pasajeros = int(request.args.get("pasajeros", 1))

        if not origen_arg or not destino_arg:
            return jsonify({"error": "Faltan parámetros"}), 400

        # 1. Intentar calcular ruta con el GRAFO (Nodos predefinidos)
        distancia, ruta = gestor_rutas.calcular_mejor_ruta(origen_arg, destino_arg)

        # Helper para parsear coordenadas
        def _parse_arg(a):
            try:
                if isinstance(a, str) and a.strip().startswith("{"):
                    return _norm_point(json.loads(a))
            except Exception:
                pass
            return _norm_point(a if isinstance(a, dict) else {"nombre": a})

        origen_pt = _parse_arg(origen_arg)
        destino_pt = _parse_arg(destino_arg)

        # 2. Lógica de Respaldo Inteligente (Haversine)
        # Se activa si:
        # A) El grafo devolvió infinito (no hay conexión o nodos desconocidos).
        # B) El grafo devolvió 0 pero las coordenadas son diferentes (bug visual).
        # C) La ruta está vacía.
        
        usar_haversine = False
        
        if distancia == float("inf") or not ruta:
            usar_haversine = True
        elif distancia == 0 or distancia == 0.0:
            # Verificar si realmente son puntos distintos
            if origen_pt and destino_pt:
                lat_diff = abs(origen_pt["lat"] - destino_pt["lat"])
                lng_diff = abs(origen_pt["lng"] - destino_pt["lng"])
                if lat_diff > 1e-6 or lng_diff > 1e-6:
                    usar_haversine = True

        if usar_haversine:
            # Intentamos calcular la distancia real con coordenadas
            if origen_pt and destino_pt and "lat" in origen_pt and "lat" in destino_pt:
                print(f"📍 Usando cálculo GPS directo para: {origen_arg} -> {destino_arg}")
                distancia = calcular_distancia_haversine(
                    origen_pt["lat"], origen_pt["lng"],
                    destino_pt["lat"], destino_pt["lng"]
                )
                # Creamos una ruta simple de dos puntos para dibujar la línea
                ruta = [origen_pt.get("nombre", "origen"), destino_pt.get("nombre", "destino")]
            else:
                # Solo si NO tenemos coordenadas, usamos el valor genérico
                print(f"⚠️ Fallo total de ruta y coordenadas. Usando 5km por defecto.")
                distancia = 5.0
                ruta = [origen_arg, destino_arg]

        # Calcular precio y tiempo (Esto aplica para grafo o haversine)
        from servicios.solicitudes_mejoradas import calcular_precio
        precio_estimado = round(calcular_precio(distancia), 2)
        
        # Estimación de tiempo: En tráfico de Lima ~3.5 mins por km (ajustable)
        tiempo_estimado = round(distancia * 3.5, 0)

        return jsonify({
            "ok": True,
            "distancia": round(distancia, 2),
            "ruta": ruta,
            "precio_estimado": precio_estimado,
            "tiempo_estimado": tiempo_estimado,
            "mensaje": "Ruta calculada exitosamente"
        }), 200

    except Exception as e:
        print("❌ Error en /api/buscar-viajes:", e)
        import traceback; traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 500

# Agregar a app.py

@app.get("/api/pasajero/viaje-activo")
@requiere_login
def api_viaje_activo_pasajero():
    """Obtiene el viaje activo del pasajero"""
    if session.get('user_type') != 'pasajero':
        return jsonify({"error": "Solo pasajeros"}), 403
    
    try:
        pasajero_id = session['user_id']
        from servicios.estados_viaje import obtener_viajes_activos_pasajero
        
        viajes_activos = obtener_viajes_activos_pasajero(pasajero_id)
        
        if not viajes_activos:
            return jsonify({"error": "No hay viaje activo"}), 404
        
        # Obtener el más reciente
        viaje = viajes_activos[0]
        
        # Enriquecer con info del conductor
        if viaje.get('conductor_id'):
            conductor = get_user_by_id_and_tipo(viaje['conductor_id'], 'conductor')
            viaje['conductor_info'] = conductor
        
        return jsonify(viaje), 200
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return jsonify({"error": str(e)}), 500


@app.post("/api/pasajero/confirmar-llegada")
@requiere_login
def api_confirmar_llegada():
    """El pasajero confirma que llegó a su destino"""
    if session.get('user_type') != 'pasajero':
        return jsonify({"error": "Solo pasajeros"}), 403
    
    try:
        data = request.get_json()
        viaje_id = data.get('viaje_id')
        pasajero_id = session['user_id']
        
        from servicios.solicitudes_mejoradas import _leer_json, SOLICITUDES_FILE, _guardar_json_atomic
        from servicios.estados_viaje import GestorEstados
        
        solicitudes = _leer_json(SOLICITUDES_FILE)
        
        for viaje in solicitudes:
            if viaje.get('id') == viaje_id and viaje.get('pasajero_id') == pasajero_id:
                if GestorEstados.actualizar_estado(
                    viaje, 'completado', pasajero_id, 'Pasajero confirmó llegada'
                ):
                    viaje['fecha_fin'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    _guardar_json_atomic(SOLICITUDES_FILE, solicitudes)
                    return jsonify({"ok": True}), 200
        
        return jsonify({"error": "Viaje no encontrado"}), 404
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/estado-viaje")
@requiere_login
def estado_viaje():
    """Vista HTML del estado del viaje"""
    if session.get('user_type') != 'pasajero':
        flash("❌ Solo los pasajeros pueden ver el estado del viaje", "error")
        return redirect(url_for('dashboard'))
    
    return render_template('estado_viaje.html')



# ============================================
# ENDPOINTS PARA GESTIÓN DE VIAJES (CONDUCTOR)
# ============================================
@app.get("/api/conductor/mis-viajes-activos")
@requiere_login
def api_mis_viajes_activos_conductor():
    if session.get('user_type') != 'conductor':
        return jsonify({"error": "Solo conductores"}), 403

    try:
        conductor_id = session["user_id"]

        from servicios.solicitudes_mejoradas import (
            obtener_viajes_conductor,
            obtener_cancelaciones_pendientes_conductor,
        )

        viajes = obtener_viajes_conductor(conductor_id) or []
        cancelaciones = obtener_cancelaciones_pendientes_conductor(conductor_id) or []

        # Devuelve viajes activos + cancelaciones que el conductor debe ver
        return jsonify(viajes + cancelaciones), 200

    except Exception as e:
        print(f"❌ Error obteniendo viajes activos: {e}")
        import traceback; traceback.print_exc()
        return jsonify({"error": str(e)}), 500



@app.post("/api/conductor/iniciar-viaje")
@requiere_login
def api_iniciar_viaje():
    """
    El conductor inicia un viaje confirmado
    """
    if session.get('user_type') != 'conductor':
        return jsonify({"error": "Solo conductores"}), 403
    
    try:
        data = request.get_json()
        solicitud_id = data.get('solicitud_id')
        conductor_id = session['user_id']
        
        print(f"📥 Solicitud de iniciar viaje #{solicitud_id} por conductor #{conductor_id}")
        
        from servicios.solicitudes_mejoradas import iniciar_viaje_conductor
        resultado = iniciar_viaje_conductor(conductor_id, solicitud_id)
        
        if resultado:
            return jsonify({
                "ok": True,
                "viaje": resultado,
                "mensaje": "Viaje iniciado correctamente"
            }), 200
        else:
            return jsonify({
                "ok": False,
                "error": "No se pudo iniciar el viaje. Verifica que esté en estado 'confirmado'."
            }), 400
            
    except Exception as e:
        print(f"❌ Error en endpoint iniciar-viaje: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.post("/api/conductor/finalizar-viaje")
@requiere_login
def api_finalizar_viaje_conductor():
    """
    El conductor finaliza un viaje en curso
    """
    if session.get('user_type') != 'conductor':
        return jsonify({"error": "Solo conductores"}), 403
    
    try:
        data = request.get_json()
        solicitud_id = data.get('solicitud_id')
        conductor_id = session['user_id']
        
        print(f"📥 Solicitud de finalizar viaje #{solicitud_id} por conductor #{conductor_id}")
        
        from servicios.solicitudes_mejoradas import finalizar_viaje_conductor
        resultado = finalizar_viaje_conductor(conductor_id, solicitud_id)
        
        if resultado:
            return jsonify({
                "ok": True,
                "viaje": resultado,
                "mensaje": "Viaje completado exitosamente"
            }), 200
        else:
            return jsonify({
                "ok": False,
                "error": "No se pudo finalizar el viaje. Debe estar en estado 'en_curso'."
            }), 404
            
    except Exception as e:
        print(f"❌ Error en endpoint finalizar-viaje: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500





@app.post("/api/conductor/cancelar-viaje")
@requiere_login
def api_cancelar_viaje_conductor():
    """
    El conductor cancela un viaje
    """
    if session.get('user_type') != 'conductor':
        return jsonify({"error": "Solo conductores"}), 403
    
    try:
        data = request.get_json()
        solicitud_id = data.get('solicitud_id')
        motivo = data.get('motivo', '')
        conductor_id = session['user_id']
        
        from servicios.solicitudes_mejoradas import cancelar_viaje_conductor
        resultado = cancelar_viaje_conductor(conductor_id, solicitud_id, motivo)
        
        if resultado:
            return jsonify({
                "ok": True,
                "mensaje": "Viaje cancelado"
            }), 200
        else:
            return jsonify({"error": "No se pudo cancelar el viaje"}), 400
            
    except Exception as e:
        print(f"❌ Error cancelando viaje: {e}")
        return jsonify({"error": str(e)}), 500

@app.post("/api/conductor/marcar-cancelacion-vista")
@requiere_login
def api_marcar_cancelacion_vista():
    """
    El conductor marca una cancelación como vista para que no vuelva a aparecer
    """
    if session.get('user_type') != 'conductor':
        return jsonify({"error": "Solo conductores"}), 403
    
    try:
        data = request.get_json()
        solicitud_id = data.get('solicitud_id')
        conductor_id = session['user_id']
        
        from servicios.solicitudes_mejoradas import marcar_cancelacion_vista_conductor
        resultado = marcar_cancelacion_vista_conductor(conductor_id, solicitud_id)
        
        if resultado:
            return jsonify({"ok": True}), 200
        else:
            return jsonify({"error": "No se pudo marcar"}), 400
            
    except Exception as e:
        print(f"❌ Error marcando cancelación: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/mis-viajes-conductor")
@requiere_login
def mis_viajes_conductor():
    """Vista de gestión de viajes para conductores"""
    if session.get('user_type') != 'conductor':
        flash("❌ Solo los conductores pueden acceder a esta página", "error")
        return redirect(url_for('dashboard'))
    
    return render_template('mis-viajes-conductor.html')

@app.get("/api/conductor/mis-ofertas-pendientes")
@requiere_login
def api_conductor_mis_ofertas_pendientes():
    """
    Devuelve:
    - pendientes: contraofertas enviadas esperando respuesta
    - confirmados: viajes confirmados listos para iniciar (para redirigir automáticamente)
    """
    if session.get('user_type') != 'conductor':
        return jsonify({"error": "Solo conductores"}), 403

    try:
        conductor_id = session['user_id']

        from servicios.solicitudes_mejoradas import _leer_json, CONTRAOFERTAS_FILE, SOLICITUDES_FILE
        contraofertas = _leer_json(CONTRAOFERTAS_FILE)
        solicitudes = _leer_json(SOLICITUDES_FILE)

        sol_by_id = {s.get("id"): s for s in solicitudes}

        # Contraofertas pendientes
        mis_pendientes = [
            c for c in contraofertas
            if c.get("conductor_id") == conductor_id and c.get("estado") == "pendiente"
        ]

        from servicios.usuarios_repo import buscar_usuario_por_id

        pendientes = []
        for c in mis_pendientes:
            item = dict(c)
            sol = sol_by_id.get(c.get("solicitud_id"))
            if sol:
                item["solicitud"] = sol
                pasajero = buscar_usuario_por_id(sol.get("pasajero_id"), "pasajero")
                if pasajero:
                    item["pasajero_nombre"] = pasajero.get("nombre", "Pasajero")
                    item["pasajero_telefono"] = pasajero.get("telefono", "N/A")
            pendientes.append(item)

        # ✅ Viajes confirmados (pasajero aceptó, listo para iniciar)
        confirmados = [
            s for s in solicitudes
            if s.get("conductor_id") == conductor_id 
            and s.get("estado") in ["confirmado", "en_curso"]
        ]

        return jsonify({
            "pendientes": pendientes,
            "confirmados": confirmados
        }), 200

    except Exception as e:
        print("❌ Error en /api/conductor/mis-ofertas-pendientes:", e)
        return jsonify({"error": str(e)}), 500



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