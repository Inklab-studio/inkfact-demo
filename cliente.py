"""
Cliente de InkFact en Python, solo con la biblioteca estándar.

    python cliente.py              # emite una boleta contra la instancia de las variables de entorno
    python cliente.py --vectores   # comprueba la firma contra los vectores publicados, sin credenciales

Variables de entorno para emitir de verdad:

    INKFACT_URL=http://localhost:3010
    INKFACT_API_KEY=ik_test_...
    INKFACT_HMAC_SECRET=...
    INKFACT_RUC=20553219702

Lo único con truco es la firma, y son cuatro pasos:

    1. Hashear el cuerpo TAL CUAL viaja (sha256, hex).
    2. Armar la cadena canónica: <timestamp>.<MÉTODO>.<ruta>.<hash del cuerpo>
    3. Firmarla con el secreto HMAC (sha256, hex).
    4. Mandarla como  X-Signature: sha256=<firma>

El error que se comete siempre: firmar un objeto y volver a serializarlo al enviarlo. Si
el JSON que firmas no es byte a byte el que mandas, la firma no vale. Aquí se serializa
UNA vez y esos mismos bytes se usan para las dos cosas.

Funciona con Python 3.8 o posterior. Sin pip, sin requests, sin nada.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys
import time
import uuid
from datetime import date
from typing import Any, Optional
from urllib import error, parse, request


def clave_idempotencia(id_de_venta: str, espacio: str = "inkfact") -> str:
    """
    Convierte el id de TU venta en una clave de idempotencia válida.

    El servicio exige un UUID, y tú tienes un "pedido_1234". Generar uno al azar en cada
    intento anularía la protección: la gracia de la clave es que sea LA MISMA cuando
    reintentas la misma venta, para que un timeout no acabe emitiendo dos comprobantes
    por un solo cobro.

    UUID versión 5: mismo texto de entrada, mismo UUID siempre, en cualquier máquina y
    en cualquier lenguaje (da exactamente el mismo que cliente.mjs y cliente.php).
    """
    # Igual que en los otros clientes: sha1 del texto, con versión 5 y variante RFC 4122.
    # No se usa uuid.uuid5 porque ese antepone un espacio de nombres de 16 bytes y daría
    # otro UUID que el cliente en Node o PHP para el mismo id de venta.
    digest = bytearray(hashlib.sha1(f"{espacio}:{id_de_venta}".encode("utf-8")).digest()[:16])
    digest[6] = (digest[6] & 0x0F) | 0x50
    digest[8] = (digest[8] & 0x3F) | 0x80
    return str(uuid.UUID(bytes=bytes(digest)))


def firmar(secreto: str, timestamp: str, metodo: str, ruta: str, cuerpo: bytes) -> str:
    """La firma, aislada para poder probarla contra los vectores publicados."""
    hash_cuerpo = hashlib.sha256(cuerpo).hexdigest()
    canonica = f"{timestamp}.{metodo.upper()}.{ruta}.{hash_cuerpo}"
    return "sha256=" + hmac.new(secreto.encode("utf-8"), canonica.encode("utf-8"), hashlib.sha256).hexdigest()


class ErrorDeInkFact(Exception):
    """Un error que devolvió el servicio, con su código estable para programar contra él."""

    def __init__(self, status: int, code: str, message: str, details: Any = None, request_id: Optional[str] = None):
        super().__init__(f"[{code}] {message}")
        self.status = status
        self.code = code
        self.message = message
        self.details = details
        self.request_id = request_id


class InkFact:
    def __init__(self, base_url: str, api_key: str, hmac_secret: str, timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.hmac_secret = hmac_secret
        self.timeout = timeout

    def emitir(self, comprobante: dict, clave: str) -> dict:
        """
        Emite un comprobante.

        `clave` es TUYA y tiene que ser la MISMA si reintentas la misma venta. Derívala de
        tu pedido con `clave_idempotencia`, no la generes al azar en cada intento.
        """
        return self._pedir("POST", "/v1/comprobantes", comprobante, {"Idempotency-Key": clave})

    def consultar(self, id: str) -> dict:
        return self._pedir("GET", f"/v1/comprobantes/{parse.quote(id)}")

    def buscar(self, texto: str) -> dict:
        """Busca por serie-número, documento del cliente o TU referencia."""
        return self._pedir("GET", "/v1/comprobantes?" + parse.urlencode({"q": texto}))

    def anulacion(self, id: str) -> dict:
        """Qué pasaría al anular, sin anular: para enseñárselo a quien confirma."""
        return self._pedir("GET", f"/v1/comprobantes/{parse.quote(id)}/anulacion")

    def anular(self, id: str, motivo: str) -> dict:
        return self._pedir("POST", f"/v1/comprobantes/{parse.quote(id)}/anular", {"reason": motivo})

    def archivo(self, id: str, cual: str, formato: Optional[str] = None) -> bytes:
        """Descarga 'xml', 'cdr' o 'pdf' (con formato a4, ticket80 o ticket58). Devuelve bytes."""
        ruta = f"/v1/comprobantes/{parse.quote(id)}/{cual}"
        if formato:
            ruta += "?" + parse.urlencode({"formato": formato})
        req = request.Request(self.base_url + ruta, headers={"X-Api-Key": self.api_key})
        try:
            with request.urlopen(req, timeout=self.timeout) as respuesta:
                return respuesta.read()
        except error.HTTPError as e:
            raise self._error(e.code, e.read()) from None

    # ------------------------------------------------------------------ interno

    def _pedir(self, metodo: str, ruta: str, cuerpo: Optional[dict] = None, extra: Optional[dict] = None) -> dict:
        # UNA sola serialización: los bytes que se firman son los que se envían.
        datos = b"" if cuerpo is None else json.dumps(cuerpo, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        timestamp = str(int(time.time()))

        cabeceras = {
            "X-Api-Key": self.api_key,
            "X-Timestamp": timestamp,
            # La ruta se firma CON su query, tal como se envía.
            "X-Signature": firmar(self.hmac_secret, timestamp, metodo, ruta, datos),
            "Content-Type": "application/json",
            **(extra or {}),
        }
        req = request.Request(self.base_url + ruta, data=datos or None, headers=cabeceras, method=metodo)

        try:
            with request.urlopen(req, timeout=self.timeout) as respuesta:
                return json.loads(respuesta.read().decode("utf-8") or "{}")
        except error.HTTPError as e:
            raise self._error(e.code, e.read()) from None
        except error.URLError as e:
            # Un fallo de red NO significa que no se emitió: puede haber llegado. Reintenta
            # con la MISMA clave de idempotencia y el servicio devuelve el comprobante que
            # ya existe (200, reused: true) en vez de crear otro.
            raise ConnectionError(f"No se pudo hablar con InkFact: {e.reason}") from e

    @staticmethod
    def _error(status: int, crudo: bytes) -> ErrorDeInkFact:
        try:
            err = json.loads(crudo.decode("utf-8")).get("error", {})
        except (ValueError, UnicodeDecodeError):
            err = {}
        # El código importa: 'validation_error' se arregla corrigiendo lo que mandaste;
        # 'signature_invalid' revisando la firma. No los trates igual.
        return ErrorDeInkFact(status, err.get("code", "error"), err.get("message", f"HTTP {status}"), err.get("details"), err.get("request_id"))


# ===========================================================================
# Comprobar la firma contra los vectores publicados (sin credenciales)
# ===========================================================================

def comprobar_vectores() -> int:
    """
    Los mismos vectores que en INTEGRACION.md y vectores-firma.json. Si esto imprime OK,
    tu implementación de la firma es correcta y lo que falte estará en otro sitio.
    """
    secreto = "sk_demo_0123456789abcdef0123456789abcdef"
    cuerpo = (
        '{"emisor_ruc":"20601234565","doc_type":"boleta","serie":"B001","issue_date":"2026-09-15",'
        '"customer":{"doc_type":"1","doc_number":"45678912","name":"MARIA QUISPE HUAMAN"},'
        '"items":[{"description":"Menú del día","quantity":1,"unit_value":12.71}]}'
    ).encode("utf-8")
    esperada = "sha256=fa0f2291267ad05e7f1f20ee7ed75728641534f6bba50ed6e92bfb52b414c830"
    obtenida = firmar(secreto, "1789000000", "POST", "/v1/comprobantes", cuerpo)

    secreto_webhook = "whsec_demo_fedcba9876543210fedcba9876543210"
    cuerpo_webhook = (
        '{"event":"comprobante.accepted","id":"9d2f5c1e-2c9a-4b8e-9a0e-3f1c2d4e5f60","full_number":"B001-00001247",'
        '"status":"accepted","external_reference":"check_8f3a1b","sunat_code":"0",'
        '"sunat_message":"La Boleta numero B001-00001247, ha sido aceptada","hash":"kL0mZ9Y3pQ2vX8sT1uW4aB6cD7eF8gH9iJ0kL1mN2oP=",'
        '"xml_url":"https://facturacion.example.com/v1/comprobantes/9d2f5c1e-2c9a-4b8e-9a0e-3f1c2d4e5f60/xml",'
        '"cdr_url":"https://facturacion.example.com/v1/comprobantes/9d2f5c1e-2c9a-4b8e-9a0e-3f1c2d4e5f60/cdr",'
        '"pdf_url":"https://facturacion.example.com/v1/comprobantes/9d2f5c1e-2c9a-4b8e-9a0e-3f1c2d4e5f60/pdf"}'
    ).encode("utf-8")
    esperada_webhook = "sha256=e4df7578fb2d35a98f8b4b630cc09e2b3bebc2c19048cb2bc574f03675b9f474"
    obtenida_webhook = "sha256=" + hmac.new(secreto_webhook.encode(), cuerpo_webhook, hashlib.sha256).hexdigest()

    ok = True
    for nombre, esp, obt in [("firma de petición", esperada, obtenida), ("firma de webhook", esperada_webhook, obtenida_webhook)]:
        if hmac.compare_digest(esp, obt):
            print(f"OK   {nombre}: {obt}")
        else:
            ok = False
            print(f"MAL  {nombre}\n     esperada {esp}\n     obtenida {obt}")
    return 0 if ok else 1


# ===========================================================================
# Ejemplo de uso
# ===========================================================================

if __name__ == "__main__":
    if "--vectores" in sys.argv:
        sys.exit(comprobar_vectores())

    inkfact = InkFact(
        base_url=os.environ.get("INKFACT_URL", "http://localhost:3010"),
        api_key=os.environ.get("INKFACT_API_KEY", ""),
        hmac_secret=os.environ.get("INKFACT_HMAC_SECRET", ""),
    )

    # En tu ERP esto sería el id de la venta. Se usa para dos cosas: como referencia para
    # encontrar el comprobante después, y —convertido a UUID— como clave de idempotencia.
    id_de_mi_venta = f"pedido_{uuid.uuid4().hex[:8]}"

    try:
        respuesta = inkfact.emitir(
            {
                "emisor_ruc": os.environ.get("INKFACT_RUC", "20553219702"),
                "doc_type": "boleta",
                "serie": "B001",
                "issue_date": date.today().isoformat(),
                "currency": "PEN",
                "operation_type": "0101",
                "customer": {
                    "doc_type": "1",  # 1 DNI, 6 RUC, 0 sin documento
                    "doc_number": "45678912",
                    "name": "MARIA QUISPE HUAMAN",
                },
                "items": [
                    {
                        "description": "Menú del día",
                        "quantity": 2,
                        "unit": "NIU",
                        "unit_value": 12.7119,  # SIN IGV. El servicio calcula el resto.
                        "igv_type": "10",
                    }
                ],
                "external_reference": id_de_mi_venta,
            },
            clave_idempotencia(id_de_mi_venta),
        )
    except ErrorDeInkFact as e:
        print(f"InkFact dijo que no: {e}  (request_id {e.request_id})")
        if e.details:
            print(json.dumps(e.details, ensure_ascii=False, indent=2))
        sys.exit(1)

    comprobante = respuesta["comprobante"]
    # Aquí ya se puede IMPRIMIR: el correlativo está asignado. SUNAT viene después.
    print(f"Emitido {comprobante['full_number']} · S/ {comprobante['totals']['total']} · {comprobante['status']}")

    ahora = inkfact.consultar(comprobante["id"])["comprobante"]
    sunat = f" · SUNAT dice: {ahora['sunat_message']}" if ahora.get("sunat_message") else ""
    print(f"Ahora: {ahora['status']}{sunat}")
