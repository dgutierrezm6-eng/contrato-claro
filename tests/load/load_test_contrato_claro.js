import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  stages: [
    { duration: '5s', target: 15 },  // Subida progresiva a 15 usuarios concurrentes
    { duration: '10s', target: 15 }, // Carga sostenida de transacciones
    { duration: '3s', target: 0 },   // Descenso controlado
  ],
  thresholds: {
    http_req_failed: ['rate<0.01'],   // SLA: menos de 1% de peticiones fallidas
    http_req_duration: ['p(95)<300'], // SLA: 95% de respuestas en menos de 300 ms
  },
};

const BASE_URL = 'http://127.0.0.1:5003';
const HEADERS = { 'Content-Type': 'application/json' };

export default function () {
  // 1. Carga de vista principal
  const resHome = http.get(`${BASE_URL}/`);
  check(resHome, { 'GET / responde 200': (r) => r.status === 200 });

  // 2. Creación concurrente de contrato con hito y escrow
  const payloadContrato = JSON.stringify({
    titulo: `Contrato Carga VU-${__VU}-IT-${__ITER}`,
    tipo: 'Servicios Profesionales',
    objeto: 'Prueba de concurrencia bajo carga',
    monto_total: 1000000,
    creador_id: 'user-freelancer-1',
    contraparte_email: 'cliente@contratoclaro.co',
    hitos: [{ titulo: 'Hito Único', monto: 1000000 }],
  });

  const resCrear = http.post(`${BASE_URL}/api/contratos/crear`, payloadContrato, { headers: HEADERS });
  check(resCrear, { 'POST /crear responde 201': (r) => r.status === 201 });

  if (resCrear.status === 201) {
    const body = resCrear.json();
    const contratoId = body.contrato_id;
    const hitoId = body.hitos[0].id;

    // 3. Depósito en custodia Escrow
    const resDep = http.post(
      `${BASE_URL}/api/escrow/depositar`,
      JSON.stringify({ contrato_id: contratoId, monto: 250000 }),
      { headers: HEADERS }
    );
    check(resDep, { 'POST /depositar responde 201': (r) => r.status === 201 });

    // 4. Liberación de hito
    const resLib = http.post(
      `${BASE_URL}/api/escrow/liberar`,
      JSON.stringify({ contrato_id: contratoId, hito_id: hitoId }),
      { headers: HEADERS }
    );
    check(resLib, { 'POST /liberar responde 200': (r) => r.status === 200 });
  }

  sleep(0.2);
}
