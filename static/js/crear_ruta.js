let map;
let conductorMarker;
let solicitudMarkers = [];
let ubicacionConductor = null;
let solicitudSeleccionada = null;
let solicitudes = [];

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
    console.log('🚗 Vista conductor inicializada');
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
    document.getElementById('btnUbicacion').addEventListener('click', obtenerUbicacion);
    document.getElementById('btnRefrescar').addEventListener('click', cargarSolicitudes);
    document.getElementById('formContraoferta').addEventListener('submit', enviarContraoferta);
    document.getElementById('btnSeleccionManual').addEventListener('click', activarSeleccionManual);

}

function obtenerUbicacion() {
    const btn = document.getElementById('btnUbicacion');
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Obteniendo...';

    if (!navigator.geolocation) {
        alert('Tu navegador no soporta geolocalización. Puedes seleccionar tu ubicación manualmente.');
        activarSeleccionManual();
        resetButton(btn);
        return;
    }

    navigator.geolocation.getCurrentPosition(
        (position) => {
            const lat = position.coords.latitude;
            const lng = position.coords.longitude;

            ubicacionConductor = { lat, lng };

            if (conductorMarker) {
                conductorMarker.setLatLng([lat, lng]);
            } else {
                conductorMarker = L.marker([lat, lng], { icon: carIcon })
                    .addTo(map)
                    .bindPopup('🚗 Tu ubicación')
                    .openPopup();
            }

            map.setView([lat, lng], 14);
            cargarSolicitudes();

            btn.innerHTML = '<i class="fas fa-check"></i> Ubicación obtenida';
            setTimeout(() => resetButton(btn), 2000);
        },
        (error) => {
            alert('No se pudo obtener tu ubicación. Puedes seleccionarla manualmente.');
            console.error(error);
            activarSeleccionManual();  // ← Aquí está el respaldo
            resetButton(btn);
        },
        { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
    );
}
function resetButton(btn) {
    btn.disabled = false;
    btn.innerHTML = '<i class="fas fa-location-crosshairs"></i> Usar mi ubicación';
}
function formatHoraViaje(hora_seleccionada, fecha_partida_str) {
    if (hora_seleccionada === 'ahora' || !fecha_partida_str) {
        return '<strong style="color: #4caf50;">Ahora</strong>';
    }

    try {
        const ahora = new Date();
        const partida = new Date(fecha_partida_str.replace(" ", "T")); // Formato ISO

        // Diferencia en milisegundos
        const diffMs = partida - ahora;

        if (diffMs <= 0) {
            return '<strong style="color: #f44336;">Recogida Inmediata (Atrasado)</strong>';
        }

        const diffMin = Math.round(diffMs / 60000); // Milisegundos a minutos

        if (diffMin <= 5) {
            return '<strong style="color: #ff9800;">En ~5 min</strong>';
        }

        return `En ${diffMin} min (aprox)`;

    } catch (e) {
        // Fallback si la fecha es inválida
        if (hora_seleccionada === '30_min') return 'En 30 min';
        if (hora_seleccionada === '60_min') return 'En 1 hora';
        return 'Ahora';
    }
}

function activarSeleccionManual() {
    alert('Haz clic en el mapa para seleccionar tu ubicación manualmente.');

    map.once('click', function(e) {
        const { lat, lng } = e.latlng;
        ubicacionConductor = { lat, lng };

        // Crear o actualizar el marcador
        if (conductorMarker) {
            conductorMarker.setLatLng([lat, lng]);
        } else {
            conductorMarker = L.marker([lat, lng], { icon: carIcon })
                .addTo(map)
                .bindPopup('🚗 Ubicación seleccionada')
                .openPopup();
        }

        map.setView([lat, lng], 14);

        cargarSolicitudes();
    });
}
async function cargarSolicitudes() {
    if (!ubicacionConductor) {
        alert('Primero activa tu ubicación');
        return;
    }

    const btn = document.getElementById('btnRefrescar');
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Cargando...';

    try {
        const url = `/api/conductor/solicitudes-cercanas?lat=${ubicacionConductor.lat}&lng=${ubicacionConductor.lng}&radio=10`;
        const res = await fetch(url, { credentials: 'same-origin' });

        if (!res.ok) throw new Error(`HTTP ${res.status}`);

        solicitudes = await res.json();

        console.log(`📍 ${solicitudes.length} solicitudes encontradas`);

        renderizarSolicitudes();
        dibujarMarcadores();

        btn.innerHTML = '<i class="fas fa-check"></i> Actualizado';
        setTimeout(() => {
            btn.innerHTML = '<i class="fas fa-sync-alt"></i> Actualizar solicitudes';
            btn.disabled = false;
        }, 1500);

    } catch (error) {
        console.error('❌ Error cargando solicitudes:', error);
        alert('Error al cargar solicitudes');
        btn.innerHTML = '<i class="fas fa-sync-alt"></i> Actualizar solicitudes';
        btn.disabled = false;
    }
}

function renderizarSolicitudes() {
    const container = document.getElementById('listaSolicitudes');

    if (solicitudes.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <i class="fas fa-inbox"></i>
                <p>No hay solicitudes disponibles en tu área</p>
            </div>
        `;
        return;
    }

    container.innerHTML = solicitudes.map(sol => {
        const distConductor = sol.distancia_conductor || 0;
        const tiempoEstimado = Math.round(sol.distancia * 3); // Aproximado: 3 min por km
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
                    <div. class="info-row">
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

function dibujarMarcadores() {
    // Limpiar marcadores anteriores
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

    // Ajustar vista para mostrar todos los marcadores
    if (solicitudMarkers.length > 0 && conductorMarker) {
        const group = L.featureGroup([conductorMarker, ...solicitudMarkers]);
        map.fitBounds(group.getBounds(), { padding: [50, 50] });
    }
}

function verDetalles(solicitudId) {
    const sol = solicitudes.find(s => s.id === solicitudId);
    if (!sol) return;

    // Centrar mapa en el origen
    if (sol.origen && sol.origen.lat && sol.origen.lng) {
        map.setView([sol.origen.lat, sol.origen.lng], 15);
    }

    console.log('📋 Detalles solicitud:', sol);
}

// =========================================
// ACEPTAR DIRECTAMENTE
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
            alert('✅ ¡Solicitud aceptada! El pasajero recibirá una notificación.');
            cargarSolicitudes(); // Recargar lista
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
            cargarSolicitudes();
        } else {
            alert('❌ ' + (data.error || 'Error al enviar'));
        }

    } catch (error) {
        console.error('❌ Error:', error);
        alert('Error al enviar la contraoferta');
    }
}

// Click fuera del modal para cerrar
document.getElementById('modalContraoferta').addEventListener('click', (e) => {
    if (e.target.id === 'modalContraoferta') {
        cerrarModal();
    }
});



