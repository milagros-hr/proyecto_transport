// Script mejorado para crear ruta (modo conductor)
(function() {
  const mapDiv = document.getElementById('map');
  if (!mapDiv) return;

  let map, conductorMarker, solicitudMarkers = [], partidaElegida = null;

  const carIcon = L.icon({
    iconUrl: 'https://cdn-icons-png.flaticon.com/512/743/743007.png',
    iconSize: [36, 36],
    iconAnchor: [18, 18]
  });

  function initMap(lat, lng) {
    map = L.map('map').setView([lat, lng], 14);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19
    }).addTo(map);

    conductorMarker = L.marker([lat, lng], { icon: carIcon })
      .addTo(map)
      .bindPopup('🚗 Tu ubicación').openPopup();
  }

  function limpiarSolicitudes() {
    solicitudMarkers.forEach(m => map.removeLayer(m));
    solicitudMarkers = [];
  }

  function mostrarSolicitudes(sols) {
    const list = document.getElementById('sol-list');
    limpiarSolicitudes();
    list.innerHTML = '';

    if (!sols.length) {
      list.innerHTML = '<div class="sol-item">No hay solicitudes disponibles.</div>';
      return;
    }

    sols.forEach((s, i) => {
      const lat = s.origen?.lat || -12.05 + Math.random() * 0.02;
      const lng = s.origen?.lng || -77.04 + Math.random() * 0.02;
      const precio = s.precio || (5 + Math.random() * 10).toFixed(2);

      const marker = L.marker([lat, lng]).addTo(map)
        .bindPopup(`<b>${s.pasajero_id || 'Pasajero ' + i}</b><br>Destino: ${s.destino?.nombre || 'Desconocido'}<br>💵 S/${precio}`);
      solicitudMarkers.push(marker);

      const item = document.createElement('div');
      item.className = 'sol-item';
      item.innerHTML = `
        <b>${s.pasajero_id || 'Pasajero ' + i}</b><br>
        Destino: ${s.destino?.nombre || 'Desconocido'}<br>
        💵 <input type="number" id="precio${i}" value="${precio}" step="0.5" style="width:60px"> 
        <button data-i="${i}">Ver</button>`;
      list.appendChild(item);

      item.querySelector('button').onclick = () => {
        map.setView([lat, lng], 16);
        marker.openPopup();
      };
    });
  }

  async function cargarSolicitudes(lat, lng) {
    try {
      const res = await fetch(`/api/solicitudes_cercanas?lat=${lat}&lng=${lng}`);
      const data = await res.json();
      mostrarSolicitudes(data);
    } catch (err) {
      console.error("Error cargando solicitudes:", err);
    }
  }

  function usarUbicacionGPS() {
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(pos => {
        const { latitude, longitude } = pos.coords;
        if (!map) initMap(latitude, longitude);
        conductorMarker.setLatLng([latitude, longitude]);
        partidaElegida = { lat: latitude, lng: longitude };
        cargarSolicitudes(latitude, longitude);
      }, () => alert("No se pudo obtener tu ubicación"));
    } else alert("Tu navegador no soporta GPS");
  }

  function elegirPartida() {
    alert("Haz clic en el mapa para definir tu punto de partida");
    map.once('click', e => {
      const { lat, lng } = e.latlng;
      if (conductorMarker) map.removeLayer(conductorMarker);
      conductorMarker = L.marker([lat, lng], { icon: carIcon }).addTo(map);
      partidaElegida = { lat, lng };
      cargarSolicitudes(lat, lng);
    });
  }

  document.getElementById('btn-ubicacion').onclick = usarUbicacionGPS;
  document.getElementById('btn-partida').onclick = elegirPartida;
  document.getElementById('btn-refresh').onclick = () => {
    if (partidaElegida) cargarSolicitudes(partidaElegida.lat, partidaElegida.lng);
  };

  initMap(-12.0464, -77.0428); // Lima por defecto
})();
