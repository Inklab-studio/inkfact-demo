# InkFact · demo y clientes de ejemplo

**InkFact** es una API de facturación electrónica SUNAT (Perú) que se instala en tu
propio servidor. Le mandas un JSON y recibes un comprobante: el sistema que la consume
nunca ve XML, ni UBL, ni SOAP, ni certificados.

Este repositorio **no es InkFact**. Es lo que se le pone delante: una página para verla
funcionar en un minuto, y tres clientes de ejemplo —PHP, Node y Python— para copiar dentro
de tu ERP.

## Verla funcionar

**Abre la página:** [inklab-studio.github.io/inkfact-demo](https://inklab-studio.github.io/inkfact-demo/)

Hay dos maneras de usarla, y la primera no necesita nada:

### 1. La muestra grabada

Pulsa **Ver una muestra** —o abre directamente
[`?muestra`](https://inklab-studio.github.io/inkfact-demo/?muestra)—. La página lleva
dentro una emisión **real**: la factura `F001-77024285`, emitida desde esta misma página
contra el ambiente de pruebas de SUNAT el 11 de setiembre de 2026, con las respuestas exactas de la API
en cada estado, el historial con sus milisegundos (de la petición al CDR: 1,6 s), el libro
con doce comprobantes reales —aceptados, anulados, pendientes de resumen— y los ficheros
que devolvió: el PDF, el XML firmado y el CDR.

No es una simulación: es una grabación, y la página lo dice en una franja que no se puede
no ver. Todo lo que se puede hacer en vivo se puede hacer sobre la grabación —ver el
ticket, descargar, abrir el JSON, pedir la consulta previa de anulación— menos anular de
verdad, y eso también lo dice.

### 2. Contra una instancia de InkFact

Con la URL de una instancia, tu `X-Api-Key` y el secreto HMAC, **Conectar** comprueba el
servicio y carga solo los emisores que esa key puede ver. Desde ahí emites boletas o
facturas de verdad —en soles o dólares, con las líneas que quieras y su afectación al
IGV—, sigues el comprobante paso a paso hasta el CDR y anulas con la consulta previa que
decide entre nota de crédito y comunicación de baja.

Todo lo que hace esta página lo hace contra la misma API que usaría tu ERP, con la misma
firma y las mismas credenciales. La instancia tiene que tener `CORS_ORIGINS` configurado
para admitir llamadas desde un navegador. Para probar contra un InkFact en tu propia
máquina (`http://localhost:3010`), descárgate `index.html` y ábrelo con doble clic: una
página en https no puede llamar a un servicio en http.

> Es un solo fichero, sin dependencias ni instalación. Tema claro por defecto, oscuro si
> se pide; escritorio y móvil. El enlace admite `?url=https://tu-instancia` para dejar el
> servidor puesto —solo la URL; las credenciales se teclean—, y `?muestra` para abrir la
> grabación directamente.

La misma página explica cómo se integra (la firma, con código en PHP, Node, Python y
curl), qué hay dentro de InkFact y cómo se compra.

## Se conecta a cualquier sistema

InkFact es una API HTTP con JSON: la consume un ERP, un POS, una tienda en línea, un SaaS
o un sistema hecho en casa, en el lenguaje que sea. Tres cosas lo hacen fácil:

- **OpenAPI 3.1 en cada instancia** (`GET /openapi.json`), generado desde las rutas y los
  esquemas reales del servidor —no una versión "documentada" y otra "real"—. Se importa
  en Postman o Insomnia, o se le pasa a un generador de clientes (`openapi-typescript`,
  `openapi-generator` para Java, C#, PHP, Python, Go…).
- **Webhooks firmados** con cada cambio de estado —comprobantes, guías, resúmenes,
  certificado por vencer—, para que el sistema no tenga que preguntar.
- **Vectores de firma** (`vectores-firma.json`) para comprobar tu implementación de la
  firma HMAC sin tener todavía credenciales: con ese secreto, ese timestamp y ese cuerpo
  tiene que salir exactamente esa firma.

Con el código de InkFact va una guía de integración completa (`INTEGRACION.md`): la
firma en siete lenguajes, idempotencia, estados, webhooks, anulación, guías, errores y
una lista de comprobación para salir a producción.

## Los clientes de ejemplo

| Fichero | Para |
|---|---|
| `cliente.php` | PHP plano. Sin Composer. Se copia dentro de un ERP en PHP y funciona |
| `cliente.mjs` | Node, sin dependencias |
| `cliente.py` | Python 3.8+, solo biblioteca estándar. `python cliente.py --vectores` comprueba la firma sin credenciales |

Los tres hacen lo mismo: arman una boleta, la firman y la mandan. Y los tres derivan la
misma clave de idempotencia del mismo id de venta, así que da igual desde cuál se
reintente. Lo único que tiene truco es la firma, y son cuatro líneas:

```
cadena  = <timestamp>.<MÉTODO>.<ruta>.<sha256hex(cuerpo)>
X-Signature: sha256=<hmac-sha256(secreto, cadena)>
```

El cuerpo se hashea **tal cual viaja**. Si lo reformateas después de firmar, la firma deja
de valer.

## Qué hace InkFact

Boletas, facturas, notas de crédito y débito, resumen diario de boletas, comunicación de
baja, retención y percepción, guías de remisión de remitente y de transportista (la baja,
que SUNAT solo admite en SOL, se registra). Correlativos sin carreras, idempotencia, cola
con reintentos y modo contingencia, webhooks firmados, PDF con QR, panel de monitoreo,
certificados cifrados en reposo, informe de fiscalización.

**Multiempresa:** cada RUC con su certificado, su ambiente y sus series. Alcance por API
key: la llave de un ERP solo ve sus propios RUC.

**Verificada contra SUNAT**: en producción con un negocio real, y en 42 casos del ambiente de
pruebas —incluidos gratuitas, ISC, exportación, moneda extranjera, descuentos globales,
crédito en cuotas, detracción, anticipos y bolsas, dentro de facturas, notas, resúmenes,
retención y percepción—, y 17 guías de remisión, de remitente y de
transportista, contra el servidor de pruebas de la GRE.

## Cómo se compra

El código fuente completo de InkFact se licencia para uso propio, con doce meses de
actualizaciones. Escríbenos y te damos acceso al repositorio.

**Contacto:** InkLab · [github.com/Inklab-studio](https://github.com/Inklab-studio)

---

Los ficheros de este repositorio son de ejemplo y se pueden usar libremente
(ver `LICENSE`). InkFact, el producto, tiene su propia licencia.
