/**
 * Cliente de InkFact en Node, sin dependencias.
 *
 *   node ejemplos/cliente.mjs
 *
 * Con las variables de entorno puestas emite una boleta de verdad contra el servicio que
 * tengas levantado:
 *
 *   INKFACT_URL=http://localhost:3010
 *   INKFACT_API_KEY=ik_beta_...
 *   INKFACT_HMAC_SECRET=...
 *   INKFACT_RUC=20553219702
 *
 * Lo único con truco es la firma, y son cuatro pasos:
 *
 *   1. Hashear el cuerpo TAL CUAL viaja (sha256, hex).
 *   2. Armar la cadena canónica: <timestamp>.<MÉTODO>.<ruta>.<hash del cuerpo>
 *   3. Firmarla con el secreto HMAC (sha256, hex).
 *   4. Mandarla como  X-Signature: sha256=<firma>
 *
 * El error que se comete siempre: firmar un objeto y volver a serializarlo al enviarlo.
 * Si el JSON que firmas no es byte a byte el que mandas, la firma no vale. Aquí se
 * serializa UNA vez y esa misma cadena se usa para las dos cosas.
 */

import { createHash, createHmac, randomUUID } from 'node:crypto';
import { pathToFileURL } from 'node:url';

/**
 * Convierte el id de TU venta en una clave de idempotencia válida.
 *
 * El servicio exige un UUID, y tú tienes un "pedido_1234". Generar uno al azar en cada
 * intento anularía la protección: la gracia de la clave de idempotencia es que sea LA
 * MISMA cuando reintentas la misma venta, para que un timeout no acabe emitiendo dos
 * comprobantes por un solo cobro.
 *
 * Esto es un UUID versión 5: mismo texto de entrada, mismo UUID siempre, en cualquier
 * máquina y en cualquier lenguaje. Guárdalo si quieres, pero no hace falta: se vuelve a
 * calcular igual.
 */
export function claveIdempotencia(idDeVenta, espacio = 'inkfact') {
  const hash = createHash('sha1').update(espacio + ':' + idDeVenta, 'utf8').digest();
  hash[6] = (hash[6] & 0x0f) | 0x50; // versión 5
  hash[8] = (hash[8] & 0x3f) | 0x80; // variante RFC 4122
  const hex = hash.subarray(0, 16).toString('hex');
  return [hex.slice(0, 8), hex.slice(8, 12), hex.slice(12, 16), hex.slice(16, 20), hex.slice(20, 32)].join('-');
}

export class InkFact {
  constructor({ baseUrl, apiKey, hmacSecret }) {
    this.baseUrl = baseUrl.replace(/\/+$/, '');
    this.apiKey = apiKey;
    this.hmacSecret = hmacSecret;
  }

  /**
   * Emite un comprobante.
   *
   * `claveIdempotencia` es TUYA y tiene que ser la MISMA si reintentas la misma venta.
   * Es lo único que impide emitir dos veces cuando la red se cae a mitad de la petición y
   * no sabes si llegó. Derívala de tu pedido, no la generes al azar en cada intento.
   */
  emitir(comprobante, claveIdempotencia) {
    return this.#pedir('POST', '/v1/comprobantes', comprobante, {
      'Idempotency-Key': claveIdempotencia,
    });
  }

  consultar(id) {
    return this.#pedir('GET', `/v1/comprobantes/${encodeURIComponent(id)}`);
  }

  /** Busca por serie-número, documento del cliente o TU referencia. */
  buscar(texto) {
    return this.#pedir('GET', `/v1/comprobantes?q=${encodeURIComponent(texto)}`);
  }

  /** Descarga un archivo: 'xml', 'cdr' o 'pdf'. Devuelve un Buffer. */
  async archivo(id, cual) {
    const respuesta = await fetch(`${this.baseUrl}/v1/comprobantes/${encodeURIComponent(id)}/${cual}`, {
      headers: { 'X-Api-Key': this.apiKey },
    });
    if (!respuesta.ok) throw new Error(`No se pudo descargar el ${cual}: HTTP ${respuesta.status}`);
    return Buffer.from(await respuesta.arrayBuffer());
  }

  // -------------------------------------------------------------- interno

  async #pedir(metodo, ruta, cuerpo = null, extra = {}) {
    // UNA sola serialización: la que se firma es la que se envía.
    const json = cuerpo === null ? '' : JSON.stringify(cuerpo);

    const timestamp = Math.floor(Date.now() / 1000).toString();
    const hashCuerpo = createHash('sha256').update(json, 'utf8').digest('hex');
    const canonica = `${timestamp}.${metodo.toUpperCase()}.${ruta}.${hashCuerpo}`;
    const firma = createHmac('sha256', this.hmacSecret).update(canonica).digest('hex');

    let respuesta;
    try {
      respuesta = await fetch(this.baseUrl + ruta, {
        method: metodo,
        headers: {
          'X-Api-Key': this.apiKey,
          'X-Timestamp': timestamp,
          'X-Signature': `sha256=${firma}`,
          'Content-Type': 'application/json',
          ...extra,
        },
        body: json === '' ? undefined : json,
      });
    } catch (error) {
      // Un fallo de red NO significa que no se emitió: puede haber llegado. Reintenta con
      // la MISMA clave de idempotencia y el servicio te devuelve el comprobante que ya
      // existe, con un 200 en vez de un 202, en lugar de crear otro.
      throw new Error(`No se pudo hablar con InkFact: ${error.message}`, { cause: error });
    }

    const datos = await respuesta.json().catch(() => ({}));

    if (!respuesta.ok) {
      const { code = 'error', message = `HTTP ${respuesta.status}` } = datos.error ?? {};
      // El código importa: 'certificate_expired' se arregla llamando al contador,
      // 'validation_error' corrigiendo lo que mandaste. No los trates igual.
      const fallo = new Error(`[${code}] ${message}`);
      fallo.code = code;
      fallo.status = respuesta.status;
      throw fallo;
    }

    return datos;
  }
}

// ===========================================================================
// Ejemplo de uso
// ===========================================================================

// pathToFileURL y no una plantilla a mano: en Windows la ruta es C:\... y la URL
// lleva TRES barras (file:///C:/...). Comparar cadenas a ojo funciona en Linux y
// falla en Windows sin decir nada: el ejemplo no imprime nada y parece roto.
if (import.meta.url === pathToFileURL(process.argv[1] ?? '').href) {
  const inkfact = new InkFact({
    baseUrl: process.env.INKFACT_URL ?? 'http://localhost:3010',
    apiKey: process.env.INKFACT_API_KEY ?? '',
    hmacSecret: process.env.INKFACT_HMAC_SECRET ?? '',
  });

  // En tu ERP esto sería el id de la venta. Se usa para dos cosas: como referencia para
  // encontrar el comprobante después, y —convertido a UUID— como clave de idempotencia.
  const idDeMiVenta = `pedido_${randomUUID().slice(0, 8)}`;

  const { comprobante } = await inkfact.emitir(
    {
      emisor_ruc: process.env.INKFACT_RUC ?? '20553219702',
      doc_type: 'boleta',
      serie: 'B001',
      issue_date: new Date().toISOString().slice(0, 10),
      currency: 'PEN',
      operation_type: '0101',
      customer: {
        doc_type: '1', // 1 DNI, 6 RUC, 0 sin documento
        doc_number: '45678912',
        name: 'MARIA QUISPE HUAMAN',
      },
      items: [
        {
          description: 'Menu del dia',
          quantity: 2,
          unit: 'NIU',
          unit_value: 12.7119, // SIN IGV. El servicio calcula el resto.
          igv_type: '10',
        },
      ],
      external_reference: idDeMiVenta,
    },
    claveIdempotencia(idDeMiVenta),
  );

  // Aquí ya se puede IMPRIMIR: el correlativo está asignado. SUNAT viene después.
  console.log(`Emitido ${comprobante.full_number} · S/ ${comprobante.totals.total} · ${comprobante.status}`);

  const { comprobante: ahora } = await inkfact.consultar(comprobante.id);
  console.log(`Ahora: ${ahora.status}${ahora.sunat_message ? ` · SUNAT dice: ${ahora.sunat_message}` : ''}`);
}
