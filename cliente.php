<?php
/**
 * Cliente de InkFact en PHP plano.
 *
 * Sin Composer, sin dependencias: solo cURL y las funciones de hash de PHP. Se copia
 * dentro de tu ERP y funciona. Si usas Laravel o Symfony, la clase es la misma; solo
 * cambia de dónde sacas la configuración.
 *
 *   php ejemplos/cliente.php
 *
 * Lo único que tiene truco es la firma, y son cuatro líneas:
 *
 *   1. Se hashea el cuerpo TAL CUAL viaja (sha256, hex).
 *   2. Se arma la cadena canónica: <timestamp>.<MÉTODO>.<ruta>.<hash del cuerpo>
 *   3. Se firma esa cadena con el secreto HMAC (sha256, hex).
 *   4. Va en la cabecera como  X-Signature: sha256=<esa firma>
 *
 * El error que se comete siempre: firmar un array y luego serializarlo otra vez al
 * enviarlo. Si el JSON que firmas no es byte a byte el que mandas, la firma no vale.
 * Por eso aquí se serializa UNA vez y se usa la misma cadena para las dos cosas.
 */

declare(strict_types=1);

/**
 * Convierte el id de TU venta en una clave de idempotencia valida.
 *
 * El servicio exige un UUID, y tu tienes un "pedido_1234". Generar uno al azar en cada
 * intento anularia la proteccion: la gracia es que sea LA MISMA cuando reintentas la
 * misma venta, para que un timeout no acabe emitiendo dos comprobantes por un cobro.
 *
 * Es un UUID version 5: mismo texto de entrada, mismo UUID siempre, en cualquier maquina
 * y en cualquier lenguaje. El equivalente en Node esta en cliente.mjs.
 *
 * Para comprobar que tu PHP da lo mismo que la referencia:
 *
 *   claveIdempotencia('pedido_1234')  ===  '37b44950-c47c-5664-a6b4-2a89aaa13c56'
 *
 * Si te sale otro, algo hace tu PHP con la codificacion del texto de entrada.
 */
function claveIdempotencia(string $idDeVenta, string $espacio = 'inkfact'): string
{
    $hash = sha1($espacio . ':' . $idDeVenta, true);
    $bytes = array_values(unpack('C*', substr($hash, 0, 16)));
    $bytes[6] = ($bytes[6] & 0x0f) | 0x50; // version 5
    $bytes[8] = ($bytes[8] & 0x3f) | 0x80; // variante RFC 4122
    $hex = bin2hex(pack('C*', ...$bytes));

    return sprintf(
        '%s-%s-%s-%s-%s',
        substr($hex, 0, 8),
        substr($hex, 8, 4),
        substr($hex, 12, 4),
        substr($hex, 16, 4),
        substr($hex, 20, 12),
    );
}

final class InkFact
{
    public function __construct(
        private string $baseUrl,
        private string $apiKey,
        private string $hmacSecret,
    ) {
        $this->baseUrl = rtrim($baseUrl, '/');
    }

    /**
     * Emite un comprobante.
     *
     * La clave de idempotencia debe ser la MISMA si reintentas la misma venta: es lo
     * único que impide emitir dos veces cuando se cae la red a mitad de la petición y no
     * sabes si llegó. Pásala por claveIdempotencia() a partir del id de tu pedido, nunca
     * generes una al azar en cada intento.
     */
    public function emitir(array $comprobante, string $claveIdempotencia): array
    {
        return $this->pedir('POST', '/v1/comprobantes', $comprobante, [
            'Idempotency-Key: ' . $claveIdempotencia,
        ]);
    }

    public function consultar(string $id): array
    {
        return $this->pedir('GET', '/v1/comprobantes/' . rawurlencode($id));
    }

    /** Busca por serie-número, documento del cliente o TU referencia. */
    public function buscar(string $texto): array
    {
        return $this->pedir('GET', '/v1/comprobantes?q=' . rawurlencode($texto));
    }

    /** Descarga un archivo: 'xml', 'cdr' o 'pdf'. Devuelve los bytes. */
    public function archivo(string $id, string $cual): string
    {
        $ch = curl_init($this->baseUrl . '/v1/comprobantes/' . rawurlencode($id) . '/' . $cual);
        curl_setopt_array($ch, [
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_HTTPHEADER => ['X-Api-Key: ' . $this->apiKey],
            CURLOPT_TIMEOUT => 30,
        ]);
        $cuerpo = curl_exec($ch);
        $estado = curl_getinfo($ch, CURLINFO_HTTP_CODE);
        curl_close($ch);

        if ($estado !== 200) {
            throw new RuntimeException("No se pudo descargar el $cual: HTTP $estado");
        }
        return $cuerpo;
    }

    // ---------------------------------------------------------------- interno

    private function pedir(string $metodo, string $ruta, ?array $cuerpo = null, array $extra = []): array
    {
        // UNA sola serialización. La que se firma es la que se envía.
        $json = $cuerpo === null ? '' : json_encode($cuerpo, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);

        $timestamp = (string) time();
        $canonica = $timestamp . '.' . strtoupper($metodo) . '.' . $ruta . '.' . hash('sha256', $json);
        $firma = hash_hmac('sha256', $canonica, $this->hmacSecret);

        $cabeceras = array_merge([
            'X-Api-Key: ' . $this->apiKey,
            'X-Timestamp: ' . $timestamp,
            'X-Signature: sha256=' . $firma,
            'Content-Type: application/json',
        ], $extra);

        $ch = curl_init($this->baseUrl . $ruta);
        curl_setopt_array($ch, [
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_CUSTOMREQUEST => strtoupper($metodo),
            CURLOPT_HTTPHEADER => $cabeceras,
            CURLOPT_TIMEOUT => 30,
        ]);
        if ($json !== '') {
            curl_setopt($ch, CURLOPT_POSTFIELDS, $json);
        }

        $respuesta = curl_exec($ch);
        if ($respuesta === false) {
            $error = curl_error($ch);
            curl_close($ch);
            // Ojo: un fallo de red NO significa que no se emitió. Puede haber llegado.
            // Reintenta con la MISMA clave de idempotencia y el servicio te devolverá el
            // comprobante que ya existe en vez de crear otro.
            throw new RuntimeException("No se pudo hablar con InkFact: $error");
        }

        $estado = curl_getinfo($ch, CURLINFO_HTTP_CODE);
        curl_close($ch);

        $datos = json_decode($respuesta, true) ?? [];

        if ($estado >= 400) {
            $mensaje = $datos['error']['message'] ?? "HTTP $estado";
            $codigo = $datos['error']['code'] ?? 'error';
            // El código importa: 'certificate_expired' se arregla llamando al contador,
            // 'validation_error' corrigiendo lo que mandaste. No los trates igual.
            throw new RuntimeException("[$codigo] $mensaje");
        }

        return $datos;
    }
}

// ===========================================================================
// Ejemplo de uso
// ===========================================================================

$inkfact = new InkFact(
    baseUrl: getenv('INKFACT_URL') ?: 'http://localhost:3010',
    apiKey: getenv('INKFACT_API_KEY') ?: 'ik_test_...',
    hmacSecret: getenv('INKFACT_HMAC_SECRET') ?: '...',
);

$idDeMiVenta = 'pedido_1234';

$respuesta = $inkfact->emitir([
    'emisor_ruc' => '20553219702',
    'doc_type' => 'boleta',
    'serie' => 'B001',
    'issue_date' => date('Y-m-d'),
    'currency' => 'PEN',
    'operation_type' => '0101',
    'customer' => [
        'doc_type' => '1',            // 1 DNI, 6 RUC, 0 sin documento
        'doc_number' => '45678912',
        'name' => 'MARIA QUISPE HUAMAN',
    ],
    'items' => [[
        'description' => 'Menu del dia',
        'quantity' => 2,
        'unit' => 'NIU',
        'unit_value' => 12.7119,      // SIN IGV. El servicio calcula el resto.
        'igv_type' => '10',
    ]],
    'external_reference' => $idDeMiVenta,
], claveIdempotencia: claveIdempotencia($idDeMiVenta));

$c = $respuesta['comprobante'];

// Aquí ya puedes IMPRIMIR. El correlativo está asignado; SUNAT viene después.
echo "Emitido {$c['full_number']} · S/ {$c['totals']['total']} · estado {$c['status']}\n";

// Y cuando quieras saber en qué quedó:
$estado = $inkfact->consultar($c['id'])['comprobante'];
echo "Ahora: {$estado['status']}";
echo $estado['sunat_message'] ? " · SUNAT dice: {$estado['sunat_message']}\n" : "\n";
