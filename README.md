# InkFact · demo y clientes de ejemplo

**InkFact** es una API de facturación electrónica SUNAT (Perú) que se instala en tu
propio servidor. Le mandas un JSON y recibes un comprobante: el sistema que la consume
nunca ve XML, ni UBL, ni SOAP, ni certificados.

Este repositorio **no es InkFact**. Es lo que se le pone delante: un demo en HTML para
probarla en un minuto, y dos clientes de ejemplo —PHP y Node— para copiar dentro de tu
ERP.

## Probar en un minuto

1. Abre `demo.html` en el navegador.
2. Pon la URL de una instancia de InkFact, tu `X-Api-Key`, el secreto HMAC y el RUC.
3. **Emitir una boleta de prueba.**

Verás cómo la API contesta al instante con el número ya asignado, cómo el comprobante
pasa a SUNAT, y podrás descargar el PDF, el XML firmado y el CDR. Debajo, el JSON exacto
que se mandó y lo que devolvió la API.

> Es un solo fichero, sin dependencias ni instalación. Funciona abriéndolo con doble clic
> o servido por HTTP. La instancia de InkFact tiene que tener `CORS_ORIGINS` configurado
> para admitir llamadas desde un navegador.

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
