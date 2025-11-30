// ============================================
// NAVEGACIÓN EXTERNA PARA CONDUCTORES
// ============================================

function navegarARecojo() {
    if (!viajeActual || !viajeActual.origen) {
        alert('No hay punto de recojo disponible');
        return;
    }

    const lat = viajeActual.origen.lat;
    const lng = viajeActual.origen.lng;
    const nombre = viajeActual.origen.nombre;

    if (confirm(`¿Abrir Google Maps para ir a:\n📍 ${nombre}?`)) {
        const url = `https://www.google.com/maps/dir/?api=1&destination=${lat},${lng}&travelmode=driving`;
        window.open(url, '_blank');
    }
}

function navegarARecojoWaze() {
    if (!viajeActual || !viajeActual.origen) {
        alert('No hay punto de recojo disponible');
        return;
    }

    const lat = viajeActual.origen.lat;
    const lng = viajeActual.origen.lng;
    const nombre = viajeActual.origen.nombre;

    if (confirm(`¿Abrir Waze para ir a:\n📍 ${nombre}?`)) {
        const url = `https://www.waze.com/ul?ll=${lat},${lng}&navigate=yes`;
        window.open(url, '_blank');
    }
}

function navegarADestino() {
    if (!viajeActual || !viajeActual.destino) {
        alert('No hay destino disponible');
        return;
    }

    const lat = viajeActual.destino.lat;
    const lng = viajeActual.destino.lng;
    const nombre = viajeActual.destino.nombre;

    if (confirm(`¿Abrir Google Maps para ir a:\n🏁 ${nombre}?`)) {
        const url = `https://www.google.com/maps/dir/?api=1&destination=${lat},${lng}&travelmode=driving`;
        window.open(url, '_blank');
    }
}

function navegarADestinoWaze() {
    if (!viajeActual || !viajeActual.destino) {
        alert('No hay destino disponible');
        return;
    }

    const lat = viajeActual.destino.lat;
    const lng = viajeActual.destino.lng;
    const nombre = viajeActual.destino.nombre;

    if (confirm(`¿Abrir Waze para ir a:\n🏁 ${nombre}?`)) {
        const url = `https://www.waze.com/ul?ll=${lat},${lng}&navigate=yes`;
        window.open(url, '_blank');
    }
}