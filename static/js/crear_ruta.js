let map;
let conductorMarker;
let solicitudMarkers = [];
let ubicacionConductor = null;
let solicitudSeleccionada = null;
let solicitudes = [];
let intervaloActualizacion = null; // Variable para el reloj de 5 seg ⏱️
let watchId = null; // Variable para el rastro del GPS 📡

const carIcon = L.icon({
    iconUrl: 'https://static.thenounproject.com/png/331565-200.png',
    iconSize: [60, 60],
    iconAnchor: [40, 40]
});

const passengerIcon = L.icon({
    iconUrl: 'https://cdn-icons-png.flaticon.com/512/747/747376.png',
    iconSize: [30, 30],
    iconAnchor: [17, 17]
});

document.addEventListener('DOMContentLoaded', init);

function init() {
    initMap();
    bindEvents();
    console.log('🚗 Vista conductor inicializada (Modo Automático)');
}

function initMap() {
    const limaCenter = [-12.0464, -77.0428];
    map = L.map('map').setView(limaCenter, 12);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors',
        maxZoom: 19
    }).addTo(map);

    console.log('🗺️ Mapa inicializado');
}

function bindEvents() {
    // Listener para GPS
    const btnUbicacion = document.getElementById('btnUbicacion');
    if (btnUbicacion) {
        btnUbicacion.addEventListener('click', activarGPSyAutoRefresco);
    }

    // Listener para Selección Manual
    const btnManual = document.getElementById('btnSeleccionManual');
    if (btnManual) {
        btnManual.addEventListener('click', activarSeleccionManual);
    }

    // Listener para el formulario de contraoferta
    const formContra = document.getElementById('formContraoferta');
    if (formContra) {
        formContra.addEventListener('submit', enviarContraoferta);
    }
}

// =====================================================
// 1. LÓGICA DE UBICACIÓN Y AUTO-REFRESCO
// =====================================================

// Opción A: Usar GPS del dispositivo
function activarGPSyAutoRefresco() {
    const btn = document.getElementById('btnUbicacion');
    
    if (!navigator.geolocation) {
        alert('Tu navegador no soporta geolocalización. Usa la selección manual.');
        return;
    }

    // Feedback visual en el botón
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-satellite-dish fa-pulse"></i> GPS Activo';
    btn.classList.remove('btn-primary');
    btn.classList.add('btn-success');

    // Desactivar eventos de click manual si estaban activos
    map.off('click');

    // Usamos watchPosition para rastreo continuo
    watchId = navigator.geolocation.watchPosition(
        (position) => {
            const lat = position.coords.latitude;
            const lng = position.coords.longitude;
            
            actualizarPosicionConductor(lat, lng);
        },
        (error) => {
            console.error("Error GPS:", error);
            alert('No se pudo obtener la señal GPS. Intenta manual.');
            btn.disabled = false;
            btn.innerHTML = '<i class="fas fa-location-crosshairs"></i> Usar mi ubicación';
            btn.classList.remove('btn-success');
            btn.classList.add('btn-primary');
        },
        { enableHighAccuracy: true, maximumAge: 0 }
    );

    // ¡Iniciar el bucle de 5 segundos!
    iniciarCicloDeActualizacion();
}

// Opción B: Seleccionar en el mapa manualmente
function activarSeleccionManual() {
    alert('Haz clic en el mapa para establecer tu ubicación.');

    // Si el GPS estaba activo, lo apagamos para no causar conflictos
    if (watchId) {
        navigator.geolocation.clearWatch(watchId);
        watchId = null;
        
        // Resetear botón de GPS visualmente
        const btnGPS = document.getElementById('btnUbicacion');
        if (btnGPS) {
            btnGPS.disabled = false;
            btnGPS.innerHTML = '<i class="fas fa-location-crosshairs"></i> Usar mi ubicación';
            btnGPS.classList.remove('btn-success');
            btnGPS.classList.add('btn-primary');
        }
    }

    // Escuchar un click en el mapa
    map.once('click', function(e) {
        const { lat, lng } = e.latlng;
        actualizarPosicionConductor(lat, lng);
        
        // ¡Iniciar el bucle de 5 segundos también aquí!
        iniciarCicloDeActualizacion();
    });
}

// Función auxiliar para mover el marcador del auto
function actualizarPosicionConductor(lat, lng) {
    ubicacionConductor = { lat, lng };

    if (conductorMarker) {
        conductorMarker.setLatLng([lat, lng]);
    } else {
        conductorMarker = L.marker([lat, lng], { icon: carIcon })
            .addTo(map)
            .bindPopup('<b>🚗 Tu ubicación</b>')
            .openPopup();
        map.setView([lat, lng], 15); // Centrar mapa la primera vez
    }
}

// El motor del relojito ⏱️
function iniciarCicloDeActualizacion() {
    // 1. Carga inmediata para no esperar
    cargarSolicitudes(true);
    verificarMisOfertas();

    // 2. Limpiar si ya existía uno previo
    if (intervaloActualizacion) clearInterval(intervaloActualizacion);

    // 3. Configurar para que se ejecute cada 5000ms (5 segundos)
    intervaloActualizacion = setInterval(() => {
        cargarSolicitudes(true); // true = modo silencioso
        verificarMisOfertas(); 
    }, 5000);

   
    console.log("✅ Búsqueda automática activada (cada 5s)");
}

// 2. Verificar si el pasajero aceptó alguna oferta
async function verificarMisOfertas() {
    try {
        const res = await fetch('/api/conductor/mis-ofertas-pendientes', { credentials: 'same-origin' });
        if (!res.ok) return;
        
        const data = await res.json();
        
        // ✅ ¡MATCH! El pasajero confirmó -> Redirigir automáticamente
        if (data.confirmados && data.confirmados.length > 0) {
            // Detener el polling
            if (intervaloActualizacion) {
                clearInterval(intervaloActualizacion);
                intervaloActualizacion = null;
            }
            
            const viaje = data.confirmados[0];
            alert(`🎉 ¡UN PASAJERO ACEPTÓ TU OFERTA!\n\nRuta: ${viaje.origen?.nombre || 'Origen'} → ${viaje.destino?.nombre || 'Destino'}\nPrecio: S/. ${viaje.precio_acordado?.toFixed(2) || viaje.precio_estandar?.toFixed(2)}\n\nSerás redirigido a tu viaje activo.`);
            window.open('/mis-viajes-conductor', '_self');
            return;
        }

        // B) Renderizar la lista de espera visual (ofertas pendientes)
        const panel = document.getElementById('panelEspera');
        const lista = document.getElementById('listaEspera');
        
        const totalPendientes = (data.pendientes || []).length;

        if (totalPendientes > 0 && panel && lista) {
            panel.style.display = 'block';
            let html = '';

            data.pendientes.forEach(oferta => {
                html += `
                    <div style="background: white; padding: 0.8rem; border-radius: 8px; border: 1px solid #ffeeba; font-size: 0.9rem;">
                        <div style="display:flex; justify-content:space-between; margin-bottom: 4px;">
                            <strong>Oferta enviada</strong>
                            <span style="color:#ff9800; font-weight:700;">S/. ${oferta.precio_ofrecido.toFixed(2)}</span>
                        </div>
                        <small style="color: #856404;"><i class="fas fa-user"></i> Esperando al pasajero...</small>
                    </div>
                `;
            });

            lista.innerHTML = html;
        } else if (panel) {
            panel.style.display = 'none';
        }

    } catch (error) {
        console.error("Error verificando ofertas:", error);
    }
}




// =====================================================
// 2. CARGA DE DATOS (API)
// =====================================================

async function cargarSolicitudes(modoSilencioso = false) {
    if (!ubicacionConductor) return;

    // Si NO es modo silencioso (ej. carga manual), podrías poner un loading si quisieras.
    // Pero como es automático, mejor no tocamos el DOM para que no parpadee.

    try {
        const url = `/api/conductor/solicitudes-cercanas?lat=${ubicacionConductor.lat}&lng=${ubicacionConductor.lng}&radio=10`;
        const res = await fetch(url, { credentials: 'same-origin' });

        if (!res.ok) throw new Error(`HTTP ${res.status}`);

        const nuevasSolicitudes = await res.json();
        solicitudes = nuevasSolicitudes;

        if (!modoSilencioso) {
            console.log(`📍 ${solicitudes.length} solicitudes encontradas`);
        }

        renderizarSolicitudes();
        dibujarMarcadores();

    } catch (error) {
        console.error('❌ Error cargando solicitudes:', error);
        // No mostramos alert en modo automático para no interrumpir
    }
}

// =====================================================
// 3. RENDERIZADO Y MAPA (Tu código original preservado)
// =====================================================

function renderizarSolicitudes() {
    const container = document.getElementById('listaSolicitudes');

    if (solicitudes.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <i class="fas fa-inbox"></i>
                <p>Buscando pasajeros cercanos...</p>
                <small style="color: #4caf50;">Actualizando automáticamente <i class="fas fa-sync fa-spin"></i></small>
            </div>
        `;
        return;
    }

    container.innerHTML = solicitudes.map(sol => {
        const distConductor = sol.distancia_conductor || 0;
        const tiempoEstimado = Math.round(sol.distancia * 3); 
        const horaViajeTexto = formatHoraViaje(sol.hora_seleccionada, sol.fecha_partida_estimada);
        
        return `
            <div class="solicitud-card" onclick="verDetalles(${sol.id})">
                <div class="solicitud-header">
                    <div class="pasajero-info">
                        <i class="fas fa-user-circle"></i>
                        ${sol.pasajero_nombre || 'Pasajero'}
                    </div>
                    <div class="precio-tag">S/. ${sol.precio_estandar.toFixed(2)}</div>
                </div>
                
                <div class="ruta-info">
                    <div class="info-row">
                        <i class="fas fa-map-marker-alt"></i>
                        <span><strong>Origen:</strong> ${sol.origen.nombre}</span>
                    </div>
                    <div class="info-row">
                        <i class="fas fa-flag-checkered"></i>
                        <span><strong>Destino:</strong> ${sol.destino.nombre}</span>
                    </div>
                    <div class="info-row">
                        <i class="fas fa-road"></i>
                        <span>${sol.distancia.toFixed(1)} km • ~${tiempoEstimado} min</span>
                    </div>
                    <div class="info-row">
                        <i class="fas fa-clock"></i>
                        <span><strong>Recoger:</strong> ${horaViajeTexto}</span>
                    </div>
                    <div class="info-row">
                        <i class="fas fa-location-arrow"></i>
                        <span class="distancia-badge">A ${distConductor.toFixed(1)} km de ti</span>
                    </div>
                </div>
                
                <div class="acciones">
                    <button class="btn btn-success btn-sm" onclick="event.stopPropagation(); aceptarDirecto(${sol.id})">
                        <i class="fas fa-check"></i> Aceptar
                    </button>
                    <button class="btn btn-warning btn-sm" onclick="event.stopPropagation(); abrirContraoferta(${sol.id})">
                        <i class="fas fa-hand-holding-usd"></i> Ofertar
                    </button>
                </div>
            </div>
        `;
    }).join('');
}

function formatHoraViaje(hora_seleccionada, fecha_partida_str) {
    if (hora_seleccionada === 'ahora' || !fecha_partida_str) {
        return '<strong style="color: #4caf50;">Ahora</strong>';
    }
    try {
        const ahora = new Date();
        const partida = new Date(fecha_partida_str.replace(" ", "T"));
        const diffMs = partida - ahora;
        if (diffMs <= 0) return '<strong style="color: #f44336;">Inmediata</strong>';
        const diffMin = Math.round(diffMs / 60000);
        if (diffMin <= 5) return '<strong style="color: #ff9800;">En ~5 min</strong>';
        return `En ${diffMin} min`;
    } catch (e) {
        if (hora_seleccionada === '30_min') return 'En 30 min';
        if (hora_seleccionada === '60_min') return 'En 1 hora';
        return 'Ahora';
    }
}

function dibujarMarcadores() {
    solicitudMarkers.forEach(m => map.removeLayer(m));
    solicitudMarkers = [];

    solicitudes.forEach(sol => {
        const origen = sol.origen;
        if (origen && origen.lat && origen.lng) {
            const marker = L.marker([origen.lat, origen.lng], { icon: passengerIcon })
                .addTo(map)
                .bindPopup(`
                    <strong>${sol.pasajero_nombre || 'Pasajero'}</strong><br>
                    Destino: ${sol.destino.nombre}<br>
                    <strong>S/. ${sol.precio_estandar.toFixed(2)}</strong>
                `);

            marker.on('click', () => verDetalles(sol.id));
            solicitudMarkers.push(marker);
        }
    });
    
    // No ajustamos la vista automáticamente siempre para no marear al conductor si está moviendo el mapa
}

function verDetalles(solicitudId) {
    const sol = solicitudes.find(s => s.id === solicitudId);
    if (!sol) return;
    if (sol.origen && sol.origen.lat && sol.origen.lng) {
        map.setView([sol.origen.lat, sol.origen.lng], 15);
    }
    console.log('📋 Detalles solicitud:', sol);
}

// =========================================
// ACEPTAR Y CONTRAOFERTAR (Sin cambios)
// =========================================

async function aceptarDirecto(solicitudId) {
    if (!confirm('¿Aceptar esta solicitud con el precio estándar?')) return;

    try {
        const res = await fetch('/api/conductor/aceptar-solicitud', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'same-origin',
            body: JSON.stringify({ solicitud_id: solicitudId })
        });

        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();

        if (data.ok) {
            alert('✅ ¡Solicitud aceptada! Ve a "Mis Viajes Activos" para iniciarla.');
            cargarSolicitudes(true); // Recargar inmediato
        } else {
            alert('❌ ' + (data.error || 'Error al aceptar'));
        }

    } catch (error) {
        console.error('❌ Error:', error);
        alert('Error al aceptar la solicitud');
    }
}

function abrirContraoferta(solicitudId) {
    const sol = solicitudes.find(s => s.id === solicitudId);
    if (!sol) return;

    solicitudSeleccionada = sol;
    document.getElementById('precioOriginal').textContent = `S/. ${sol.precio_estandar.toFixed(2)}`;
    document.getElementById('precioOfrecido').value = sol.precio_estandar.toFixed(2);
    document.getElementById('mensaje').value = '';
    document.getElementById('modalContraoferta').classList.add('active');
}

function cerrarModal() {
    document.getElementById('modalContraoferta').classList.remove('active');
    solicitudSeleccionada = null;
}

async function enviarContraoferta(e) {
    e.preventDefault();
    if (!solicitudSeleccionada) return;

    const precioOfrecido = parseFloat(document.getElementById('precioOfrecido').value);
    const mensaje = document.getElementById('mensaje').value.trim();

    if (precioOfrecido <= 0) {
        alert('El precio debe ser mayor a 0');
        return;
    }

    try {
        const res = await fetch('/api/conductor/contraoferta', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'same-origin',
            body: JSON.stringify({
                solicitud_id: solicitudSeleccionada.id,
                precio_ofrecido: precioOfrecido,
                mensaje: mensaje
            })
        });

        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();

        if (data.ok) {
            alert('✅ ¡Contraoferta enviada! El pasajero la verá en su app.');
            cerrarModal();
            cargarSolicitudes(true);
        } else {
            alert('❌ ' + (data.error || 'Error al enviar'));
        }

    } catch (error) {
        console.error('❌ Error:', error);
        alert('Error al enviar la contraoferta');
    }
}

// Click fuera del modal para cerrar
const modal = document.getElementById('modalContraoferta');
if (modal) {
    modal.addEventListener('click', (e) => {
        if (e.target.id === 'modalContraoferta') {
            cerrarModal();
        }
    });
}