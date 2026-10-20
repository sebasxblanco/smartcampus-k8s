// Pide los datos al backend a través de nginx (/api/...) y los pinta en las tablas.

async function pedir(ruta, opciones) {
  const respuesta = await fetch(`/api${ruta}`, opciones);
  if (!respuesta.ok) {
    const cuerpo = await respuesta.json().catch(() => ({}));
    throw new Error(cuerpo.detail || `HTTP ${respuesta.status}`);
  }
  return respuesta.status === 204 ? null : respuesta.json();
}

function fila(celdas) {
  const tr = document.createElement("tr");
  for (const valor of celdas) {
    const td = document.createElement("td");
    td.textContent = valor;
    tr.appendChild(td);
  }
  return tr;
}

async function cargar() {
  const estado = document.getElementById("estado");
  try {
    const [info, aulas, reservas] = await Promise.all([
      pedir("/info"), pedir("/rooms"), pedir("/bookings"),
    ]);
    estado.textContent = `Backend conectado · entorno: ${info.env}`;
    estado.className = "estado";

    const nombres = Object.fromEntries(aulas.map((a) => [a.id, a.nombre]));
    document.getElementById("aulas").replaceChildren(
      ...aulas.map((a) => fila([a.id, a.nombre, a.edificio, a.capacidad, a.equipamiento.join(", ")])),
    );
    document.getElementById("reservas").replaceChildren(
      ...reservas.map((r) => fila([r.id, nombres[r.aula_id] ?? r.aula_id, r.usuario, r.fecha, r.hora_inicio, r.hora_fin])),
    );
  } catch (error) {
    estado.textContent = `No se pudo conectar con el backend: ${error.message}`;
    estado.className = "estado error";
  }
}

document.getElementById("form-aula").addEventListener("submit", async (evento) => {
  evento.preventDefault();
  const datos = new FormData(evento.target);
  const aula = {
    nombre: datos.get("nombre"),
    edificio: datos.get("edificio"),
    capacidad: Number(datos.get("capacidad")),
    equipamiento: datos.get("equipamiento").split(",").map((e) => e.trim()).filter(Boolean),
  };
  try {
    await pedir("/rooms", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(aula),
    });
    evento.target.reset();
    cargar();
  } catch (error) {
    alert(`No se pudo crear el aula: ${error.message}`);
  }
});

cargar();
