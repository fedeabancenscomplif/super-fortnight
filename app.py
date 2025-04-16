from flask import Flask, request, jsonify
import subprocess
import json
import os
import logging
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET
import base64
from zeep import Client

app = Flask(__name__)

# Configuración de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Variables globales para almacenar token y sign
token_data = {
    'token': None,
    'sign': None,
    'expiration': None
}

def obtener_token_sign():
    """Obtiene un nuevo token y sign de AFIP"""
    try:
        # Ejecutar el script de autenticación
        result = subprocess.run(
            ['python3', '../auth_afip.py'],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            logger.error(f"Error al obtener token: {result.stderr}")
            return None, None
            
        # Parsear la respuesta XML
        root = ET.fromstring(result.stdout)
        token = root.find('.//token').text
        sign = root.find('.//sign').text
        
        # Calcular tiempo de expiración (12 horas)
        expiration = datetime.now() + timedelta(hours=12)
        
        return token, sign, expiration
        
    except Exception as e:
        logger.error(f"Error al obtener token y sign: {str(e)}")
        return None, None, None

def verificar_token():
    """Verifica si el token actual es válido o necesita renovación"""
    global token_data
    
    if (token_data['token'] is None or 
        token_data['sign'] is None or 
        token_data['expiration'] is None or
        datetime.now() >= token_data['expiration']):
        
        logger.info("Token expirado o no existe, obteniendo nuevo token")
        token, sign, expiration = obtener_token_sign()
        
        if token and sign and expiration:
            token_data = {
                'token': token,
                'sign': sign,
                'expiration': expiration
            }
            return True
        return False
    
    return True

@app.route('/auth', methods=['GET'])
def auth():
    """Endpoint para obtener el token y sign actuales"""
    if verificar_token():
        return jsonify({
            'token': token_data['token'],
            'sign': token_data['sign'],
            'expiration': token_data['expiration'].isoformat()
        })
    else:
        return jsonify({'error': 'No se pudo obtener el token'}), 500

@app.route('/emitir_factura', methods=['POST'])
def emitir_factura():
    """Endpoint para emitir una factura"""
    if not verificar_token():
        return jsonify({'error': 'No se pudo obtener el token válido'}), 500
        
    try:
        data = request.json
        # Aquí iría la lógica para emitir la factura usando token_data['token'] y token_data['sign']
        # Por ahora solo devolvemos un mensaje de ejemplo
        return jsonify({
            'mensaje': 'Factura emitida correctamente',
            'token': token_data['token'],
            'sign': token_data['sign']
        })
    except Exception as e:
        logger.error(f"Error al emitir factura: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True) 