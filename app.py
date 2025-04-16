from flask import Flask, request, jsonify
import logging
from afip_service import AFIPService

app = Flask(__name__)

# Configuración de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Inicializar servicio AFIP
afip_service = AFIPService()

# Almacenamiento temporal del token y sign
current_auth = None

@app.route('/auth', methods=['GET'])
def auth():
    """Endpoint para obtener el token y sign actuales"""
    try:
        global current_auth
        current_auth = afip_service.obtener_token_sign()
        return jsonify(current_auth)
    except Exception as e:
        logger.error(f"Error en endpoint /auth: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/emitir_factura', methods=['POST'])
def emitir_factura():
    """Endpoint para emitir una factura"""
    try:
        data = request.json
        
        # Validar campos requeridos
        required_fields = ['doc_nro', 'cbte_desde', 'cbte_hasta', 'imp_total', 'imp_neto']
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            return jsonify({"error": f"Faltan campos requeridos: {', '.join(missing_fields)}"}), 400
        
        # Si no hay token válido, obtener uno nuevo
        global current_auth
        if not current_auth:
            current_auth = afip_service.obtener_token_sign()
        
        # Emitir factura usando el token actual
        result = afip_service.emitir_factura(data)
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error en endpoint /emitir_factura: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True) 