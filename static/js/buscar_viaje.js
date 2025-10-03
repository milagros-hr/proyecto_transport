// ========================================
// TRANSPORT - BUSCAR VIAJE (Frontend)
// ========================================

const API = {
  nodos: '/api/grafo/nodos',
  buscar: '/api/buscar-viajes',
  solicitar: '/api/solicitar'
};

// ---- Fallback de nodos si el endpoint no responde ----
const FALLBACK_NODES = [
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
  {"id":"cercado","nombre":"Cercado de Lima","lat":-12.0464,"lng":-77.0428}
];

// Variables globales
let map;
let nodes = [];
let nodesByName = new Map();
let nodesById = new Map();
let nodeMarkers = [];
let routeLayer = null;

let mode = 'origen'; // 'origen' | 'destino'
let originMarker = null;
let destinationMarker = null;

// Para mantener la selección real de cada campo
// - Lo que ve el usuario: dirección (input.value + <small>)
// - Lo que usa el backend: nombre del nodo (input.dataset.node)
const state = {
  origen: { lat: null, lng: null, nodeName: null },
  destino: { lat: null, lng: null, nodeName: null },
};

let debounceTimer = null;

// ========================================
// INICIALIZACIÓN
// ========================================

document.addEventListener('DOMContentLoaded', init);

async function init() {
  console.log('🚀 Iniciando aplicación...');
  initMap();
  await fetchNodes();
  bindUI();
  setMinDate();
  console.log('✅ Aplicación inicializada correctamente');
}

// ========================================
// MAPA (LEAFLET)
// ========================================

function initMap() {
  const limaCenter = [-12.0464, -77.0428];
  map = L.map('map').setView(limaCenter, 11);

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© OpenStreetMap contributors',
    maxZoom: 18
  }).addTo(map);

  // Click en el mapa = usar coords exactas (no el nombre del nodo)
  map.on('click', async (e) => {
    const { lat, lng } = e.latlng;
    await setPointFromCoords(mode, lat, lng);
  });

  console.log('🗺️ Mapa inicializado');
}

function getMarkerIcon(kind) {
  const color = kind === 'origen' ? '#4CAF50' : '#f44336';
  return L.divIcon({
    html: `<div style="background:${color};border-radius:50%;width:20px;height:20px;border:3px solid white;box-shadow:0 2px 5px rgba(0,0,0,.3);"></div>`,
    iconSize: [20, 20],
    className: `${kind}-marker`
  });
}

// ========================================
// CARGA DE NODOS + DIBUJO EN MAPA
// ========================================

async function fetchNodes() {
  try {
    const res = await fetch(API.nodos, { credentials: 'same-origin' });
    if (!res.ok) {
      console.warn('⚠️ /api/grafo/nodos no OK, usando fallback.');
      nodes = FALLBACK_NODES;
      indexAndDraw();
      return;
    }
    const data = await res.json();
    nodes = (Array.isArray(data) && data.length) ? data : FALLBACK_NODES;
    indexAndDraw();
  } catch (err) {
    console.error('❌ Error al cargar nodos:', err);
    nodes = FALLBACK_NODES;
    indexAndDraw();
    showStatus('error', 'No se pudieron cargar los puntos del mapa');
  }
}

function indexAndDraw() {
  nodesByName.clear();
  nodesById.clear();
  nodes.forEach(n => {
    if (n.nombre) nodesByName.set(n.nombre, n);
    if (n.id) nodesById.set(n.id, n);
  });
  drawNodes();
  setupAutocomplete();
}

function drawNodes() {
  nodeMarkers.forEach(m => map.removeLayer(m));
  nodeMarkers = [];

  nodes.forEach(node => {
    if (!node.lat || !node.lng) return;

    const marker = L.circleMarker([node.lat, node.lng], {
      radius: 6, fillColor: '#ffd93d', color: '#333', weight: 2,
      opacity: 1, fillOpacity: 0.85
    });

    marker.bindTooltip(node.nombre, { permanent: false, direction: 'top', className: 'node-tooltip' });

    // Click en un nodo -> usar las coords del nodo
    marker.on('click', async () => {
      await setPointFromNode(mode, node);
    });

    marker.addTo(map);
    nodeMarkers.push(marker);
  });

  console.log(`🎯 ${nodeMarkers.length} nodos dibujados en el mapa`);
}

function setupAutocomplete() {
  const datalist = document.getElementById('nodosList');
  datalist.innerHTML = nodes.map(n => `<option value="${n.nombre}">`).join('');
  console.log('🔤 Autocompletado configurado');
}

// ========================================
// SELECCIÓN DE PUNTOS
// ========================================

// 1) Desde coords exactas (mapa / geolocalización / forward geocode)
async function setPointFromCoords(kind, lat, lng) {
  // 1. Poner marcador en la posición real
  placeMarker(kind, lat, lng);

  // 2. Mostrar dirección humana debajo del input
  const addr = await reverseGeocode(lat, lng);
  const label = document.getElementById(kind + 'Address');
  if (label) label.textContent = addr || `${lat.toFixed(5)}, ${lng.toFixed(5)}`;

  // 3. El input muestra la dirección humana (NO el nombre del nodo)
  const input = document.getElementById(kind);
  input.value = addr || `${lat.toFixed(5)}, ${lng.toFixed(5)}`;

  // 4. Asociar internamente el nodo más cercano (para el backend)
  const nearest = snapToNearestNode(lat, lng);
  if (nearest) {
    input.dataset.node = nearest.nombre;
    state[kind] = { lat, lng, nodeName: nearest.nombre };
  } else {
    delete input.dataset.node;
    state[kind] = { lat, lng, nodeName: null };
  }

  // 5. Centrar mapa
  map.setView([lat, lng], 14);

  checkFormValidity();
  console.log(`✅ ${kind} establecido por coords → nodo: ${input.dataset.node || 'N/A'}`);
}

// 2) Desde un nodo (click en marcador de nodo o elegiste nodo del datalist)
async function setPointFromNode(kind, node) {
  if (!node || !node.lat || !node.lng) return;

  // 1. Poner marcador en el nodo
function placeMarker(kind, lat, lng) {
  const icon = getMarkerIcon(kind);
  let marker = (kind === 'origen') ? originMarker : destinationMarker;

  if (!marker) {
    marker = L.marker([lat, lng], { icon, draggable: true }).addTo(map);
    // Al soltar el marcador, recalcula dirección y nodo cercano
    marker.on('dragend', async (e) => {
      const p = e.target.getLatLng();
      await setPointFromCoords(kind, p.lat, p.lng); // reusa tu lógica (NO recrea el marker)
    });
    if (kind === 'origen') originMarker = marker;
    else destinationMarker = marker;
  } else {
    marker.setLatLng([lat, lng]);
  }
}


  // 2. Dirección humana (reverse geocode del propio nodo)
  const addr = await reverseGeocode(node.lat, node.lng);
  const label = document.getElementById(kind + 'Address');
  if (label) label.textContent = addr || node.nombre;

  // 3. El input muestra la dirección humana (más friendly)
  const input = document.getElementById(kind);
  input.value = addr || node.nombre;

  // 4. Asociar internamente el nodo (para el backend)
  input.dataset.node = node.nombre;
  state[kind] = { lat: node.lat, lng: node.lng, nodeName: node.nombre };

  // 5. Centrar mapa
  map.setView([node.lat, node.lng], 14);

  checkFormValidity();
  console.log(`✅ ${kind} establecido por nodo → ${node.nombre}`);
}

function placeMarker(kind, lat, lng) {
  const icon = getMarkerIcon(kind);
  if (kind === 'origen') {
    if (originMarker) map.removeLayer(originMarker);
    originMarker = L.marker([lat, lng], { icon }).addTo(map);
  } else {
    if (destinationMarker) map.removeLayer(destinationMarker);
    destinationMarker = L.marker([lat, lng], { icon }).addTo(map);
  }
}

// ========================================
// GEOLOCALIZACIÓN
// ========================================

async function getCurrentLocation() {
  const btn = document.getElementById('getLocationBtn');
  btn.disabled = true;
  btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
  showStatus('warning', 'Obteniendo tu ubicación...');

  if (!navigator.geolocation) {
    showStatus('error', 'Tu navegador no soporta geolocalización');
    resetLocationBtn();
    return;
  }

  navigator.geolocation.getCurrentPosition(
    async (position) => {
      const lat = position.coords.latitude;
      const lng = position.coords.longitude;

      await setPointFromCoords('origen', lat, lng);
      showStatus('success', 'Ubicación obtenida correctamente');

      // Cambiar modo a destino
      document.querySelector('input[name="setMode"][value="destino"]').checked = true;
      mode = 'destino';

      btn.innerHTML = '<i class="fas fa-check"></i>';
      setTimeout(resetLocationBtn, 1500);
    },
    (error) => {
      let msg = 'Error al obtener ubicación';
      switch (error.code) {
        case error.PERMISSION_DENIED: msg = 'Permiso de ubicación denegado'; break;
        case error.POSITION_UNAVAILABLE: msg = 'Ubicación no disponible'; break;
        case error.TIMEOUT: msg = 'Tiempo de espera agotado'; break;
      }
      showStatus('error', msg);
      resetLocationBtn();
    },
    { enableHighAccuracy: true, timeout: 10000, maximumAge: 300000 }
  );
}

function resetLocationBtn() {
  const btn = document.getElementById('getLocationBtn');
  btn.disabled = false;
  btn.innerHTML = '<i class="fas fa-location-arrow"></i>';
}

// ========================================
// AUTOCOMPLETE / ESCRITURA EN INPUTS
// ========================================

function bindUI() {
  // Cambiar modo origen/destino
  document.querySelectorAll('input[name="setMode"]').forEach(radio => {
    radio.addEventListener('change', (e) => {
      mode = e.target.value;
      console.log(`🎯 Modo cambiado a: ${mode}`);
    });
  });

  // Botón de geolocalización
  document.getElementById('getLocationBtn').addEventListener('click', getCurrentLocation);

  // Formulario de búsqueda
  document.getElementById('searchForm').addEventListener('submit', buscarViajes);

  // Inputs: si el valor coincide con un nodo -> setPointFromNode
  // de lo contrario -> intentar forward geocode
  ['origen', 'destino'].forEach((id) => {
    const el = document.getElementById(id);
    el.addEventListener('input', () => {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(async () => {
        const text = el.value.trim();
        if (!text) {
          delete el.dataset.node;
          document.getElementById(id + 'Address').textContent = '';
          checkFormValidity();
          return;
        }

        // Si coincide exactamente con un nodo
        const node = nodesByName.get(text);
        if (node) {
          await setPointFromNode(id, node);
          return;
        }

        // Intentar forward geocoding (p.ej. "Av. Arequipa 1234")
        if (text.length >= 3) {
          const pos = await forwardGeocode(text);
          if (pos) {
            await setPointFromCoords(id, pos.lat, pos.lng);
          } else {
            // No se encontró: quitamos el dataset.node para no habilitar el botón
            delete el.dataset.node;
            showStatus('warning', 'No se pudo ubicar esa dirección. Prueba con otra referencia.');
            checkFormValidity();
          }
        }
      }, 350);
    });
  });
}

// ========================================
// GEOCODERS (OSM/Nominatim)
// ========================================

async function reverseGeocode(lat, lng) {
  try {
    const url = `https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat=${lat}&lon=${lng}&addressdetails=1&namedetails=1&extratags=1&accept-language=es&zoom=19`;
    const r = await fetch(url, { headers: { 'Accept-Language': 'es' } });
    const j = await r.json();
    return formatAddress(j) || (j && j.display_name) || null;
  } catch {
    return null;
  }
}

function formatAddress(j) {
  if (!j || !j.address) return null;
  const a = j.address;

  // Línea 1: calle + número (o nombre de lugar si existe)
  const line1 = [
    a.road || a.pedestrian || a.footway || a.path || a.cycleway || a.residential || a.highway || j.name
  ].filter(Boolean).join(' ');
  const house = a.house_number ? ` ${a.house_number}` : '';

  // Línea 2: barrio/zona + ciudad + código postal
  const area = a.neighbourhood || a.suburb || a.village || a.town || a.city_district;
  const city = a.city || a.town || a.municipality || a.county;
  const line2 = [area, city, a.state, a.postcode].filter(Boolean).join(', ');

  const full = [line1 + house, line2].filter(Boolean).join(', ');
  return full || j.display_name || null;
}


async function forwardGeocode(query) {
  try {
    // viewbox: left,top,right,bottom (aprox Lima)
    const viewbox = '-77.20,-11.90,-76.80,-12.25';
    const url = `https://nominatim.openstreetmap.org/search?format=jsonv2&q=${encodeURIComponent(query)}&addressdetails=1&accept-language=es&limit=1&countrycodes=pe&viewbox=${viewbox}&bounded=1`;
    const r = await fetch(url, { headers: { 'Accept-Language': 'es' } });
    const j = await r.json();
    if (Array.isArray(j) && j.length > 0) {
      const { lat, lon } = j[0];
      return { lat: parseFloat(lat), lng: parseFloat(lon) };
    }
    return null;
  } catch {
    return null;
  }
}


// ========================================
// SNAP AL NODO MÁS CERCANO (HAVERSINE)
// ========================================

function snapToNearestNode(lat, lng) {
  if (nodes.length === 0) return null;
  const valid = nodes.filter(n => n.lat && n.lng);
  if (!valid.length) return null;

  let nearest = null;
  let minDist = Infinity;
  for (const n of valid) {
    const d = haversine(lat, lng, n.lat, n.lng);
    if (d < minDist) { minDist = d; nearest = n; }
  }
  return nearest;
}

function haversine(lat1, lng1, lat2, lng2) {
  const R = 6371; // km
  const dLat = (lat2 - lat1) * Math.PI / 180;
  const dLng = (lng2 - lng1) * Math.PI / 180;
  const a = Math.sin(dLat/2)**2 +
            Math.cos(lat1 * Math.PI/180) * Math.cos(lat2 * Math.PI/180) *
            Math.sin(dLng/2)**2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

// ========================================
// BÚSQUEDA DE VIAJES
// ========================================

async function buscarViajes(e) {
  e.preventDefault();

  const origenInput = document.getElementById('origen');
  const destinoInput = document.getElementById('destino');
  const pasajeros = document.getElementById('pasajeros').value;

  const origenNode = origenInput.dataset.node || '';
  const destinoNode = destinoInput.dataset.node || '';

  if (!origenNode || !destinoNode || !pasajeros) {
    showStatus('error', 'Completa origen y destino válidos (deben asociarse a un nodo).');
    return;
  }

  const searchBtn = document.getElementById('searchBtn');
  searchBtn.disabled = true;
  searchBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Buscando...';

  try {
    const url = new URL(API.buscar, window.location.origin);
    // IMPORTANTE: mandamos los NOMBRES DE NODO (no las direcciones)
    url.searchParams.set('origen', origenNode);
    url.searchParams.set('destino', destinoNode);
    url.searchParams.set('pasajeros', pasajeros);

    const res = await fetch(url, { credentials: 'same-origin' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    // Dibujar ruta si viene del backend
    if (data.ruta && data.ruta.length > 0) {
      drawRoute(data.ruta);
    } else if (routeLayer) {
      map.removeLayer(routeLayer);
      routeLayer = null;
    }

    displayResults(data.resultados || [], data.distancia);
  } catch (err) {
    console.error('❌ Error en búsqueda:', err);
    showStatus('error', 'Error al buscar viajes. Intenta de nuevo.');
    document.getElementById('results').style.display = 'none';
  } finally {
    searchBtn.disabled = false;
    searchBtn.innerHTML = '<i class="fas fa-search"></i> Buscar Viajes Disponibles';
  }
}

// ========================================
// DIBUJO DE RUTA
// ========================================

function drawRoute(ruta) {
  if (routeLayer) map.removeLayer(routeLayer);

  let coords = [];

  if (Array.isArray(ruta) && ruta.length > 0) {
    if (typeof ruta[0] === 'string') {
      // Ruta por nombres de nodo
      coords = ruta
        .map(nombre => nodesByName.get(nombre))
        .filter(n => n && n.lat && n.lng)
        .map(n => [n.lat, n.lng]);
    } else if (Array.isArray(ruta[0]) && ruta[0].length === 2) {
      // Ruta por coordenadas [[lat,lng], ...]
      coords = ruta;
    }
  }

  if (coords.length < 2) {
    console.warn('⚠️ No hay suficientes coordenadas para dibujar la ruta');
    return;
  }

  routeLayer = L.polyline(coords, {
    color: '#ff9800',
    weight: 5,
    opacity: 0.85,
    smoothFactor: 1
  }).addTo(map);

  map.fitBounds(routeLayer.getBounds(), { padding: [50, 50] });
  console.log('🛣️ Ruta dibujada:', coords.length, 'puntos');
}

// ========================================
// RESULTADOS Y RESERVA
// ========================================

function displayResults(resultados, distancia) {
  const resultsDiv = document.getElementById('results');
  const resultsList = document.getElementById('resultsList');

  if (!resultados || resultados.length === 0) {
    resultsList.innerHTML = `
      <div style="padding: 1rem; text-align: center; color: #666;">
        <i class="fas fa-info-circle"></i>
        No se encontraron viajes disponibles para esta ruta.
      </div>`;
    resultsDiv.style.display = 'block';
    return;
  }

  resultsList.innerHTML = resultados.map((r, idx) => `
    <div class="result-item">
      <div class="result-header">
        <span class="conductor-name"><i class="fas fa-user-circle"></i> ${r.conductor || 'Conductor'}</span>
        <span class="price">${r.precio || 'S/ --'}</span>
      </div>
      <div class="route-info"><i class="fas fa-route"></i> ${r.origen || ''} → ${r.destino || ''}</div>
      <div class="route-info">
        <i class="fas fa-clock"></i> ${r.tiempo || '--'} •
        <i class="fas fa-car"></i> ${r.vehiculo || 'Vehículo'} •
        <i class="fas fa-users"></i> ${r.asientos || 0} asientos
      </div>
      ${distancia ? `<div class="route-info"><i class="fas fa-road"></i> ${distancia.toFixed(1)} km</div>` : ''}
      <button class="btn-select" onclick="reservarViaje(${r.id || idx}, ${idx})">
        <i class="fas fa-check-circle"></i> Seleccionar Viaje
      </button>
    </div>
  `).join('');

  resultsDiv.style.display = 'block';
  console.log(`✅ ${resultados.length} resultados mostrados`);
}

async function reservarViaje(conductorId, resultIdx) {
  const resultados = document.querySelectorAll('.result-item');
  if (resultIdx >= resultados.length) return;

  const origenNode = document.getElementById('origen').dataset.node || '';
  const destinoNode = document.getElementById('destino').dataset.node || '';

  const btn = resultados[resultIdx].querySelector('.btn-select');
  const originalHTML = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Reservando...';

  try {
    const payload = {
      conductor_id: conductorId,
      origen: origenNode,
      destino: destinoNode,
      ruta: [],
      distancia: 0
    };

    const res = await fetch(API.solicitar, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify(payload)
    });

    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    if (data.ok) {
      showStatus('success', '¡Viaje reservado con éxito!');
      setTimeout(() => { resetForm(); }, 1500);
    } else {
      throw new Error(data.error || 'Error desconocido');
    }
  } catch (err) {
    console.error('❌ Error al reservar:', err);
    showStatus('error', 'Error al reservar el viaje. Intenta de nuevo.');
    btn.disabled = false;
    btn.innerHTML = originalHTML;
  }
}

// ========================================
// UTILIDADES
// ========================================

function setMinDate() {
  const fechaInput = document.getElementById('fecha');
  const now = new Date();
  now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
  fechaInput.min = now.toISOString().slice(0, 16);
  fechaInput.value = now.toISOString().slice(0, 16);
}

function checkFormValidity() {
  const origenNode = document.getElementById('origen').dataset.node || '';
  const destinoNode = document.getElementById('destino').dataset.node || '';
  const pasajeros = document.getElementById('pasajeros').value;
  document.getElementById('searchBtn').disabled = !(origenNode && destinoNode && pasajeros);
}

function showStatus(type, message) {
  const statusDiv = document.getElementById('locationStatus');
  const icons = { success: 'fa-check-circle', warning: 'fa-spinner fa-spin', error: 'fa-exclamation-triangle' };
  statusDiv.innerHTML = `
    <div class="status ${type}">
      <i class="fas ${icons[type]}"></i>
      ${message}
    </div>`;
  if (type !== 'error') {
    setTimeout(() => { statusDiv.innerHTML = ''; }, 5000);
  }
}

function resetForm() {
  // Limpiar inputs visibles (direcciones)
  document.getElementById('origen').value = '';
  document.getElementById('destino').value = '';
  document.getElementById('origenAddress').textContent = '';
  document.getElementById('destinoAddress').textContent = '';
  delete document.getElementById('origen').dataset.node;
  delete document.getElementById('destino').dataset.node;

  // Limpiar markers y ruta
  if (originMarker) { map.removeLayer(originMarker); originMarker = null; }
  if (destinationMarker) { map.removeLayer(destinationMarker); destinationMarker = null; }
  if (routeLayer) { map.removeLayer(routeLayer); routeLayer = null; }

  // Ocultar resultados
  document.getElementById('results').style.display = 'none';

  // Resetear modo
  document.querySelector('input[name="setMode"][value="origen"]').checked = true;
  mode = 'origen';

  checkFormValidity();
  console.log('🔄 Formulario reseteado');
}
