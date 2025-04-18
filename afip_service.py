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
        self.cuit = "20427202438" #os.getenv('CUIT')
        
        # Verificar que los certificados existan
        if not all([self.cert_base64, self.key_base64, self.cuit]):
            raise ValueError("Faltan variables de entorno: CERTIFICADO, CLAVE o CUIT")
        
        # Convertir CUIT a entero y validar
        try:
            self.cuit = int(self.cuit)
            if len(str(self.cuit)) != 11:
                raise ValueError("El CUIT debe tener 11 dígitos")
        except ValueError as e:
            raise ValueError(f"Error en el CUIT: {str(e)}")
        
        # URLs de los servicios AFIP
        self.wsaa_url = 'https://wsaahomo.afip.gov.ar/ws/services/LoginCms?WSDL'
        self.wsfe_url = 'https://wswhomo.afip.gov.ar/wsfev1/service.asmx?WSDL'
        
        # Almacenamiento del token actual
        self.current_auth = None

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

    def _is_token_valid(self):
        """Verifica si el token actual es válido"""
        if not self.current_auth or 'expiration' not in self.current_auth:
            return False
        try:
            expiration = datetime.fromisoformat(self.current_auth['expiration'])
            return expiration > datetime.now(timezone.utc)
        except Exception as e:
            logger.error(f"Error al verificar validez del token: {str(e)}")
            return False

    def _obtener_token_sign(self):
        """Obtiene un nuevo token y sign de AFIP"""
        try:
            # Crear archivos temporales para los certificados
            cert_temp, key_temp = self._write_temp_certificates()
            logger.info("Certificados temporales creados correctamente")
            
            # Generar XML de login con hora de Argentina
            dt_now = datetime.now(ARG_TIMEZONE)
            unique_id = dt_now.strftime('%y%m%d%H%M')
            gen_time = (dt_now - timedelta(minutes=10)).strftime('%Y-%m-%dT%H:%M:%S')
            exp_time = (dt_now + timedelta(minutes=10)).strftime('%Y-%m-%dT%H:%M:%S')

            logger.info(f"Generando XML con unique_id: {unique_id}, gen_time: {gen_time}, exp_time: {exp_time}")

            root = ET.Element('loginTicketRequest')
            header = ET.SubElement(root, 'header')
            ET.SubElement(header, 'uniqueId').text = unique_id
            ET.SubElement(header, 'generationTime').text = gen_time
            ET.SubElement(header, 'expirationTime').text = exp_time
            ET.SubElement(root, 'service').text = 'wsfe'

            xml_str = ET.tostring(root, encoding='unicode')
            logger.info(f"XML generado: {xml_str}")
            
            # Crear archivo temporal para el XML
            xml_temp = tempfile.NamedTemporaryFile(delete=False, suffix='.xml')
            xml_temp.write(xml_str.encode())
            xml_temp.close()
            
            # Firmar con OpenSSL
            logger.info("Firmando XML con OpenSSL")
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
            logger.info("XML firmado correctamente")
            
            # Limpiar archivos temporales
            self._cleanup_temp_files(cert_temp, key_temp, xml_temp.name)
            
            # Obtener token y sign
            logger.info("Conectando con WSAA")
            client = Client(self.wsaa_url)
            response = client.service.loginCms(cms_b64)
            
            # Parsear respuesta
            root = ET.fromstring(response)
            token = root.find('.//token').text
            sign = root.find('.//sign').text
            expiration = datetime.now(ARG_TIMEZONE) + timedelta(hours=12)
            
            logger.info("Token y sign obtenidos correctamente")
            return {
                'token': token,
                'sign': sign,
                'expiration': expiration.isoformat()
            }
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Error al firmar con OpenSSL: {str(e)}")
            logger.error(f"Stderr: {e.stderr.decode()}")
            raise
        except Exception as e:
            error_msg = str(e)
            if "El CEE ya posee un TA valido" in error_msg:
                logger.warning("Token válido existente detectado")
                raise ValueError("Ya existe un token válido. Por favor, espera a que expire antes de solicitar uno nuevo.")
            logger.error(f"Error al obtener token y sign: {str(e)}")
            raise

    def emitir_factura(self, datos_factura):
        """Emite una factura electrónica"""
        try:
            # Verificar si necesitamos un nuevo token
            if not self._is_token_valid():
                logger.info("Token inválido o expirado, obteniendo uno nuevo")
                self.current_auth = self._obtener_token_sign()
            else:
                logger.info("Reutilizando token existente")
            
            # Crear cliente WSFE
            client = Client(self.wsfe_url)
            
            # Preparar datos de la factura
            factura_data = {
                'Auth': {
                    'Token': self.current_auth['token'],
                    'Sign': self.current_auth['sign'],
                    'Cuit': '20427202438'
                },
                'FeDetReq': {
                    'FECAEDetRequest': {
                        'Concepto': datos_factura.get('concepto', 1),
                        'DocTipo': datos_factura.get('doc_tipo', 80),
                        'DocNro': int(datos_factura.get('doc_nro')),
                        'CbteDesde': int(datos_factura.get('cbte_desde')),
                        'CbteHasta': int(datos_factura.get('cbte_hasta')),
                        'CbteFch': datetime.now(ARG_TIMEZONE).strftime('%Y%m%d'),
                        'ImpTotal': float(datos_factura.get('imp_total')),
                        'ImpTotConc': float(datos_factura.get('imp_tot_conc', 0)),
                        'ImpNeto': float(datos_factura.get('imp_neto')),
                        'ImpOpEx': float(datos_factura.get('imp_op_ex', 0)),
                        'ImpIVA': float(datos_factura.get('imp_iva', 0)),
                        'ImpTrib': float(datos_factura.get('imp_trib', 0)),
                        'MonId': datos_factura.get('mon_id', 'PES'),
                        'MonCot': float(datos_factura.get('mon_cot', 1))
                    }
                }
            }
            
            logger.info(f"Datos de factura preparados: {factura_data}")
            
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