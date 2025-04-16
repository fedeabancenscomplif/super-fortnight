from flask import Flask, request, jsonify
import logging
from afip_service import AFIPService
from datetime import datetime, timezone

app = Flask(__name__)

# Configuración de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Inicializar servicio AFIP
afip_service = AFIPService()

# Almacenamiento temporal del token, sign y expiración
current_auth = None

def is_token_valid():
    """Verifica si el token actual es válido"""
    global current_auth
    if not current_auth or 'expiration' not in current_auth:
        return False
    try:
        expiration = datetime.fromisoformat(current_auth['expiration'])
        return expiration > datetime.now(timezone.utc)
    except Exception as e:
        logger.error(f"Error al verificar validez del token: {str(e)}")
        return False

@app.route('/auth', methods=['GET'])
def auth():
    """Endpoint para obtener el token y sign actuales"""
    try:
        logger.info("Iniciando proceso de autenticación")
        global current_auth
        
        # Si hay un token válido, devolverlo
        if is_token_valid():
            logger.info("Token válido existente, reutilizando")
            return jsonify(current_auth)
        
        # Obtener nuevo token
        logger.info("Obteniendo nuevo token")
        current_auth = afip_service.obtener_token_sign()
        logger.info("Token y sign obtenidos correctamente")
        return jsonify(current_auth)
        
    except Exception as e:
        logger.error(f"Error en endpoint /auth: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/emitir_factura', methods=['POST'])
def emitir_factura():
    """Endpoint para emitir una factura"""
    try:
        logger.info("Iniciando proceso de emisión de factura")
        data = request.json
        logger.info(f"Datos recibidos: {data}")
        
        # Validar campos requeridos
        required_fields = ['doc_nro', 'cbte_desde', 'cbte_hasta', 'imp_total', 'imp_neto']
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            logger.error(f"Campos faltantes: {missing_fields}")
            return jsonify({"error": f"Faltan campos requeridos: {', '.join(missing_fields)}"}), 400
        
        # Verificar token
        global current_auth
        if not is_token_valid():
            logger.info("Token inválido o expirado, obteniendo uno nuevo")
            current_auth = afip_service.obtener_token_sign()
        
        logger.info("Emitiendo factura con token válido")
        # Emitir factura usando el token actual
        result = afip_service.emitir_factura(
            data,
            token=current_auth['token'],
            sign=current_auth['sign']
        )
        logger.info(f"Factura emitida correctamente: {result}")
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error en endpoint /emitir_factura: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True) 