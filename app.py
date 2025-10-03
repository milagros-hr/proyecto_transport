from flask import Flask, render_template, request, redirect, url_for, flash, session
import json
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'tu_clave_secreta_aqui'  

# Archivos para almacenar datos
PASAJEROS_FILE = 'data/pasajeros.json'
CONDUCTORES_FILE = 'data/conductores.json'

def crear_directorio_data():
    """Crea el directorio data si no existe"""
    if not os.path.exists('data'):
        os.makedirs('data')
        print("📁 Directorio 'data' creado")

def cargar_datos(archivo):
    """Carga datos desde un archivo JSON"""
    try:
        with open(archivo, 'r', encoding='utf-8') as f:
            datos = json.load(f)
            print(f"📖 Cargados {len(datos)} registros desde {archivo}")
            return datos
    except FileNotFoundError:
        print(f"⚠️  Archivo {archivo} no encontrado, creando lista vacía")
        return []
    except json.JSONDecodeError:
        print(f"❌ Error al leer JSON en {archivo}, creando lista vacía")
        return []

def guardar_datos(archivo, datos):
    """Guarda datos en un archivo JSON"""
    try:
        crear_directorio_data()
        with open(archivo, 'w', encoding='utf-8') as f:
            json.dump(datos, f, ensure_ascii=False, indent=2)
        print(f"✅ Guardados {len(datos)} registros en {archivo}")
        return True
    except Exception as e:
        print(f"❌ Error al guardar en {archivo}: {e}")
        return False

def generar_id(datos):
    """Genera un ID único basado en los datos existentes"""
    if not datos:
        return 1
    return max([usuario['id'] for usuario in datos]) + 1

def buscar_usuario_por_correo(correo, tipo):
    """Busca un usuario por correo y tipo"""
    archivo = PASAJEROS_FILE if tipo == 'pasajero' else CONDUCTORES_FILE
    datos = cargar_datos(archivo)
    
    for usuario in datos:
        if usuario['correo'].lower() == correo.lower():
            return usuario
    return None

def buscar_usuario_por_id(user_id):
    """Busca un usuario por ID en ambos archivos"""
    # Buscar en pasajeros
    pasajeros = cargar_datos(PASAJEROS_FILE)
    for usuario in pasajeros:
        if usuario['id'] == user_id:
            return usuario
    
    # Buscar en conductores
    conductores = cargar_datos(CONDUCTORES_FILE)
    for usuario in conductores:
        if usuario['id'] == user_id:
            return usuario
    
    return None

def usuario_existe(correo, tipo):
    """Verifica si un usuario ya existe"""
    return buscar_usuario_por_correo(correo, tipo) is not None

def requiere_login(f):
    """Decorador para rutas que requieren login"""
    from functools import wraps
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("❌ Debes iniciar sesión primero", "warning")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route("/")
def inicio():
    # Si ya está logueado, ir al dashboard
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template("index.html")

@app.route("/registro", methods=["GET", "POST"])
def registro():
    if request.method == "POST":
        # Campos básicos
        nombre = request.form.get("nombre", "").strip()
        correo = request.form.get("correo", "").strip()
        telefono = request.form.get("telefono", "").strip()

        # Detectar tipo de usuario
        tipo = request.form.get("tipo", "").strip()
        if not tipo:
            tipo = request.form.get("tipo_usuario", "").strip()

        # Si es conductor, pedir más datos
        licencia = request.form.get("licencia", "").strip() if tipo == "conductor" else None
        placa    = request.form.get("placa", "").strip() if tipo == "conductor" else None
        modelo   = request.form.get("modelo", "").strip() if tipo == "conductor" else None
        color    = request.form.get("color", "").strip() if tipo == "conductor" else None

        # Validaciones
        campos_faltantes = []
        if not nombre: campos_faltantes.append("nombre")
        if not correo: campos_faltantes.append("correo")
        if not telefono: campos_faltantes.append("telefono")
        if not tipo: campos_faltantes.append("tipo de usuario")
        
        if tipo == "conductor":
            if not licencia: campos_faltantes.append("licencia")
            if not placa: campos_faltantes.append("placa")
            if not modelo: campos_faltantes.append("modelo")
            if not color: campos_faltantes.append("color")

        if campos_faltantes:
            flash(f"❌ Faltan los siguientes campos: {', '.join(campos_faltantes)}", "error")
            return render_template("registro.html")

        if tipo not in ['pasajero', 'conductor']:
            flash("❌ Tipo de usuario no válido", "error")
            return render_template("registro.html")

        if usuario_existe(correo, tipo):
            flash(f"❌ Ya existe un {tipo} registrado con ese correo electrónico", "error")
            return render_template("registro.html")

        # Archivo según tipo
        archivo = PASAJEROS_FILE if tipo == 'pasajero' else CONDUCTORES_FILE
        datos = cargar_datos(archivo)

        # Crear nuevo usuario
        nuevo_usuario = {
            'id': generar_id(datos),
            'nombre': nombre,
            'correo': correo,
            'telefono': telefono,
            'tipo': tipo,
            'fecha_registro': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        # Si es conductor, añadir campos extra
        if tipo == "conductor":
            nuevo_usuario.update({
                'licencia': licencia,
                'placa': placa,
                'modelo': modelo,
                'color': color
            })

        datos.append(nuevo_usuario)

        if guardar_datos(archivo, datos):
            flash(f"✅ {tipo.capitalize()} registrado exitosamente", "success")
            return redirect(url_for("login"))
        else:
            flash("❌ Error al guardar los datos. Inténtalo de nuevo.", "error")
            return render_template("registro.html")

    return render_template("registro.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        correo = request.form.get("email", "").strip()  # CAMBIADO: usar 'email' como en tu HTML
        tipo = request.form.get("tipo", "").strip()
        
        # Si no viene tipo del formulario, intentar ambos
        if not tipo:
            tipo = request.form.get("tipo_usuario", "").strip()

        print(f"🔑 Intento de login: {correo} como {tipo}")
        print(f"📝 Datos del formulario: {dict(request.form)}")

        # Validaciones básicas
        if not correo:
            flash("❌ El correo electrónico es obligatorio", "error")
            return render_template("login.html")

        # Si no viene tipo, buscar en ambos archivos
        usuario = None
        if tipo and tipo in ['pasajero', 'conductor']:
            usuario = buscar_usuario_por_correo(correo, tipo)
        else:
            # Buscar en ambos tipos si no se especifica
            usuario = buscar_usuario_por_correo(correo, 'pasajero')
            if not usuario:
                usuario = buscar_usuario_por_correo(correo, 'conductor')

        if usuario:
            # CREAR SESIÓN
            session['user_id'] = usuario['id']
            session['user_name'] = usuario['nombre']
            session['user_email'] = usuario['correo']
            session['user_type'] = usuario['tipo']
            session['user_phone'] = usuario['telefono']
            session['user_date'] = usuario['fecha_registro']
            
            # Hacer sesión permanente si marcó recordar
            if request.form.get('remember'):
                session.permanent = True
                
            print(f"✅ Login exitoso para {usuario['nombre']} - Sesión creada")
            flash(f"✅ Bienvenido, {usuario['nombre']}!", "success")
            return redirect(url_for('dashboard'))
        else:
            print(f"❌ Usuario no encontrado: {correo}")
            flash(f"❌ No se encontró un usuario registrado con ese correo", "error")
            return render_template("login.html")

    return render_template("login.html")

@app.route("/dashboard")
@requiere_login
def dashboard():
    """Dashboard principal - requiere login"""
    # Obtener usuario actual desde la sesión
    usuario_actual = buscar_usuario_por_id(session['user_id'])
    
    if not usuario_actual:
        # Si no se encuentra el usuario, limpiar sesión
        session.clear()
        flash("❌ Error: Usuario no encontrado", "error")
        return redirect(url_for('login'))
    
    print(f"📊 Cargando dashboard para: {usuario_actual['nombre']}")
    
    # Obtener estadísticas
    stats = obtener_estadisticas()
    
    return render_template("dashboard.html", 
                         usuario=usuario_actual, 
                         stats=stats)

@app.route("/logout")
def logout():
    """Cerrar sesión"""
    user_name = session.get('user_name', 'Usuario')
    session.clear()
    flash(f"👋 ¡Hasta luego, {user_name}!", "info")
    return redirect(url_for('inicio'))

# RUTAS PARA LOS BOTONES DEL DASHBOARD
@app.route("/buscar-viaje")
@requiere_login

def buscar_viaje():
    if session.get('user_type') != 'pasajero':
        flash("❌ Solo los pasajeros pueden buscar viajes", "error")
        return redirect(url_for('dashboard'))
    return render_template('buscar_viaje.html')  # ← Cambiar por el archivo que acabas de crear




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
    """Ruta para ver todos los usuarios registrados (para debugging)"""
    pasajeros = cargar_datos(PASAJEROS_FILE)
    conductores = cargar_datos(CONDUCTORES_FILE)
    
    return render_template("usuarios.html", 
                         pasajeros=pasajeros, 
                         conductores=conductores)

@app.route("/limpiar_datos")
def limpiar_datos():
    """Ruta para limpiar todos los datos (para debugging)"""
    crear_directorio_data()
    
    if guardar_datos(PASAJEROS_FILE, []) and guardar_datos(CONDUCTORES_FILE, []):
        flash("🗑️ Todos los datos han sido eliminados", "info")
    else:
        flash("❌ Error al limpiar los datos", "error")
        
    return redirect(url_for("inicio"))

# Función para mostrar estadísticas básicas
def obtener_estadisticas():
    pasajeros = cargar_datos(PASAJEROS_FILE)
    conductores = cargar_datos(CONDUCTORES_FILE)
    
    return {
        'total_pasajeros': len(pasajeros),
        'total_conductores': len(conductores),
        'total_usuarios': len(pasajeros) + len(conductores)
    }



@app.context_processor
def inject_stats():
    """Inyecta estadísticas en todas las plantillas"""
    return {'stats': obtener_estadisticas()}

if __name__ == "__main__":
    # Crear directorio data al iniciar
    crear_directorio_data()
    print("🚖 TransPort iniciado - Los datos se guardan en archivos JSON")
    print(f"📁 Pasajeros: {os.path.abspath(PASAJEROS_FILE)}")
    print(f"📁 Conductores: {os.path.abspath(CONDUCTORES_FILE)}")
    
    # Verificar permisos de escritura
    try:
        test_file = 'data/test_write.json'
        with open(test_file, 'w') as f:
            json.dump({"test": True}, f)
        os.remove(test_file)
        print("✅ Permisos de escritura verificados")
    except Exception as e:
        print(f"❌ Error de permisos: {e}")
    
    print("\n=== PARA PROBAR ===")
    print("1. Registra un usuario en /registro")
    print("2. Haz login en /login")  
    print("3. Accede al dashboard automáticamente")
    print("==================\n")
    
    app.run(debug=True)