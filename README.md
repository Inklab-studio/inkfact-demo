# InkFact · demo y clientes de ejemplo

**InkFact** es una API de facturación electrónica SUNAT (Perú) que se instala en tu
propio servidor. Le mandas un JSON y recibes un comprobante: el sistema que la consume
nunca ve XML, ni UBL, ni SOAP, ni certificados.

Este repositorio **no es InkFact**. Es lo que se le pone delante: un demo en HTML para
probarla en un minuto, y dos clientes de ejemplo —PHP y Node— para copiar dentro de tu
ERP.

## Probar en dos minutos

1. Abre `demo.html` en el navegador.
2. **Conectar**: la URL de una instancia de InkFact, tu `X-Api-Key` y el secreto HMAC. La
   página comprueba el servicio y carga **solo los emisores que esa key puede ver** —el
   alcance por API key, delante de tus ojos—.
3. **Emitir**: boleta o factura, en soles o dólares, con las líneas que quieras y su
   afectación al IGV —gravado, exonerado, inafecto, gratuito—. Los totales se calculan en
   vivo para orientar; los que valen los calcula el servidor.
4. **Ver qué pasó**: la API contesta al instante con el número ya asignado, y la página
   sigue el comprobante paso a paso —numerado, firmado, en cola, enviado, aceptado— con
   el código y el mensaje exactos de SUNAT. PDF en A4 o ticket, XML firmado, CDR, y el
   JSON tal cual llegó a la API.
5. **Los últimos comprobantes del emisor**, con sus descargas y **Anular**: la API dice
   primero qué va a hacer —nota de crédito o comunicación de baja, según el tipo y el
   plazo— y luego se confirma con un motivo.

Todo lo que hace esta página lo hace contra la misma API que usaría tu ERP, con la misma
firma y las mismas credenciales. Verificado contra la beta real de SUNAT: una factura
emitida desde aquí vuelve con *"ha sido aceptada"* y su CDR.

> Es un solo fichero, sin dependencias ni instalación. Funciona abriéndolo con doble clic
> o servido por HTTP, en escritorio y en el móvil, en claro y en oscuro. La instancia de
> InkFact tiene que tener `CORS_ORIGINS` configurado para admitir llamadas desde un
> navegador.

## Los clientes de ejemplo

| Fichero | Para |
|---|---|
| `cliente.php` | PHP plano. Sin Composer. Se copia dentro de un ERP en PHP y funciona |
| `cliente.mjs` | Node, sin dependencias |

Los dos hacen lo mismo: arman una boleta, la firman y la mandan. Lo único que tiene truco
es la firma, y son cuatro líneas:

```
cadena  = <timestamp>.<MÉTODO>.<ruta>.<sha256hex(cuerpo)>
X-Signature: sha256=<hmac-sha256(secreto, cadena)>
```

El cuerpo se hashea **tal cual viaja**. Si lo reformateas después de firmar, la firma deja
de valer.

## Qué hace InkFact

Boletas, facturas, notas de crédito y débito, resumen diario de boletas, comunicación de
baja, guías de remisión con reversión. Correlativos sin carreras, idempotencia, cola con
reintentos y modo contingencia, webhooks firmados, PDF con QR, panel de monitoreo,
certificados cifrados en reposo, informe de fiscalización.

**Multiempresa:** cada RUC con su certificado, su ambiente y sus series. Alcance por API
key: la llave de un ERP solo ve sus propios RUC.

**Verificada contra el ambiente beta de SUNAT** en 31 comprobantes distintos —incluidos
gratuitas, ISC, exportación, moneda extranjera y descuentos globales, dentro de facturas,
notas y resúmenes—.

## Cómo se compra

El código fuente completo de InkFact se licencia para uso propio, con doce meses de
actualizaciones. Escríbenos y te damos acceso al repositorio.

**Contacto:** InkLab · [github.com/Inklab-studio](https://github.com/Inklab-studio)

---

Los ficheros de este repositorio son de ejemplo y se pueden usar libremente
(ver `LICENSE`). InkFact, el producto, tiene su propia licencia.
