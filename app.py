from flask import Flask, request, jsonify
import logging
from afip_service import AFIPService

app = Flask(__name__)

# Configuración de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Inicializar servicio AFIP
afip_service = AFIPService()

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
        
        # Emitir factura (la autenticación se maneja internamente)
        result = afip_service.emitir_factura(data)
        logger.info(f"Factura emitida correctamente: {result}")
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error en endpoint /emitir_factura: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True) 