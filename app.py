from flask import Flask, request, jsonify
import logging
from afip_service import AFIPService

app = Flask(__name__)

# Configuración de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Inicializar servicio AFIP
afip_service = AFIPService()

@app.route('/auth', methods=['GET'])
def auth():
    """Endpoint para obtener el token y sign actuales"""
    try:
        auth_data = afip_service.obtener_token_sign()
        return jsonify(auth_data)
    except Exception as e:
        logger.error(f"Error en endpoint /auth: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/emitir_factura', methods=['POST'])
def emitir_factura():
    """Endpoint para emitir una factura"""
    try:
        datos_factura = request.json
        
        # Validar datos requeridos
        required_fields = ['doc_nro', 'imp_total', 'imp_neto']
        missing_fields = [field for field in required_fields if field not in datos_factura]
        
        if missing_fields:
            return jsonify({
                'error': 'Faltan campos requeridos',
                'campos_faltantes': missing_fields
            }), 400
        
        # Emitir factura
        resultado = afip_service.emitir_factura(datos_factura)
        return jsonify(resultado)
        
    except Exception as e:
        logger.error(f"Error en endpoint /emitir_factura: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True) 