import os
import logging
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
import base64
from zeep import Client
import tempfile

# Configuración de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuración de zona horaria
ARG_TIMEZONE = timezone(timedelta(hours=-3))

class AFIPService:
    def __init__(self):
        # Obtener los certificados desde variables de entorno en base64
        self.cert_base64 = os.getenv('CERTIFICADO')
        self.key_base64 = os.getenv('CLAVE')
        self.cuit = os.getenv('CUIT')
        
        # URLs de los servicios AFIP
        self.wsaa_url = 'https://wsaahomo.afip.gov.ar/ws/services/LoginCms?WSDL'
        self.wsfe_url = 'https://wswhomo.afip.gov.ar/wsfev1/service.asmx?WSDL'
        
        # Verificar que los certificados existan
        if not all([self.cert_base64, self.key_base64, self.cuit]):
            raise ValueError("Faltan variables de entorno: CERTIFICADO, CLAVE o CUIT")

    def _write_temp_certificates(self):
        """Escribe los certificados en archivos temporales desde base64"""
        try:
            # Crear archivos temporales
            cert_file = tempfile.NamedTemporaryFile(delete=False, suffix='.crt')
            key_file = tempfile.NamedTemporaryFile(delete=False, suffix='.key')
            
            # Decodificar y escribir contenido de los certificados
            cert_content = base64.b64decode(self.cert_base64)
            key_content = base64.b64decode(self.key_base64)
            
            cert_file.write(cert_content)
            key_file.write(key_content)
            
            # Cerrar archivos
            cert_file.close()
            key_file.close()
            
            return cert_file.name, key_file.name
            
        except Exception as e:
            logger.error(f"Error al escribir certificados temporales: {str(e)}")
            raise

    def _cleanup_temp_files(self, *files):
        """Limpia los archivos temporales"""
        for file in files:
            try:
                if os.path.exists(file):
                    os.unlink(file)
            except Exception as e:
                logger.warning(f"Error al eliminar archivo temporal {file}: {str(e)}")

    def obtener_token_sign(self):
        """Obtiene un nuevo token y sign de AFIP"""
        try:
            # Crear archivos temporales para los certificados
            cert_temp, key_temp = self._write_temp_certificates()
            
            # Generar XML de login con hora de Argentina
            dt_now = datetime.now(ARG_TIMEZONE)
            unique_id = dt_now.strftime('%y%m%d%H%M')
            gen_time = (dt_now - timedelta(minutes=10)).strftime('%Y-%m-%dT%H:%M:%S')
            exp_time = (dt_now + timedelta(minutes=10)).strftime('%Y-%m-%dT%H:%M:%S')

            root = ET.Element('loginTicketRequest')
            header = ET.SubElement(root, 'header')
            ET.SubElement(header, 'uniqueId').text = unique_id
            ET.SubElement(header, 'generationTime').text = gen_time
            ET.SubElement(header, 'expirationTime').text = exp_time
            ET.SubElement(root, 'service').text = 'wsfe'

            xml_str = ET.tostring(root, encoding='unicode')
            
            # Crear archivo temporal para el XML
            xml_temp = tempfile.NamedTemporaryFile(delete=False, suffix='.xml')
            xml_temp.write(xml_str.encode())
            xml_temp.close()
            
            # Firmar con OpenSSL
            result = subprocess.run([
                'openssl', 'cms', '-sign',
                '-in', xml_temp.name,
                '-signer', cert_temp,
                '-inkey', key_temp,
                '-nodetach',
                '-outform', 'der'
            ], capture_output=True, check=True)
            
            cms_der = result.stdout
            cms_b64 = base64.b64encode(cms_der).decode('ascii')
            
            # Limpiar archivos temporales
            self._cleanup_temp_files(cert_temp, key_temp, xml_temp.name)
            
            # Obtener token y sign
            client = Client(self.wsaa_url)
            response = client.service.loginCms(cms_b64)
            
            # Parsear respuesta
            root = ET.fromstring(response)
            token = root.find('.//token').text
            sign = root.find('.//sign').text
            expiration = datetime.now(ARG_TIMEZONE) + timedelta(hours=12)
            
            return {
                'token': token,
                'sign': sign,
                'expiration': expiration.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error al obtener token y sign: {str(e)}")
            raise

    def emitir_factura(self, datos_factura):
        """Emite una factura electrónica"""
        try:
            # Obtener token y sign
            auth_data = self.obtener_token_sign()
            
            # Crear cliente WSFE
            client = Client(self.wsfe_url)
            
            # Preparar datos de la factura
            factura_data = {
                'Auth': {
                    'Token': auth_data['token'],
                    'Sign': auth_data['sign'],
                    'Cuit': self.cuit
                },
                'FeDetReq': {
                    'FECAEDetRequest': {
                        'Concepto': datos_factura.get('concepto', 1),
                        'DocTipo': datos_factura.get('doc_tipo', 80),
                        'DocNro': datos_factura.get('doc_nro'),
                        'CbteDesde': datos_factura.get('cbte_desde'),
                        'CbteHasta': datos_factura.get('cbte_hasta'),
                        'CbteFch': datetime.now(ARG_TIMEZONE).strftime('%Y%m%d'),
                        'ImpTotal': datos_factura.get('imp_total'),
                        'ImpTotConc': datos_factura.get('imp_tot_conc', 0),
                        'ImpNeto': datos_factura.get('imp_neto'),
                        'ImpOpEx': datos_factura.get('imp_op_ex', 0),
                        'ImpIVA': datos_factura.get('imp_iva', 0),
                        'ImpTrib': datos_factura.get('imp_trib', 0),
                        'MonId': datos_factura.get('mon_id', 'PES'),
                        'MonCot': datos_factura.get('mon_cot', 1)
                    }
                }
            }
            
            # Emitir factura
            response = client.service.FECAESolicitar(factura_data)
            
            return {
                'cae': response.FeDetResp.FECAEDetResponse[0].CAE,
                'fecha_vencimiento': response.FeDetResp.FECAEDetResponse[0].CAEFchVto,
                'resultado': response.FeDetResp.FECAEDetResponse[0].Resultado
            }
            
        except Exception as e:
            logger.error(f"Error al emitir factura: {str(e)}")
            raise 