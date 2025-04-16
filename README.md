# API AFIP

API para autenticación y facturación con AFIP.

## Estructura del Proyecto

```
api_afip/
├── app.py              # Aplicación Flask principal
├── requirements.txt    # Dependencias de Python
├── static/            # Archivos estáticos
└── templates/         # Plantillas HTML
```

## Requisitos

- Python 3.7+
- Certificado AFIP
- Clave privada AFIP

## Despliegue en Render

1. Crear una cuenta en [Render](https://render.com/)
2. Crear un nuevo "Web Service"
3. Conectar con tu repositorio de GitHub
4. Configurar el servicio:
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app`
5. Agregar las variables de entorno:
   - `CERTIFICADO_PATH`: Ruta al certificado
   - `CLAVE_PRIVADA_PATH`: Ruta a la clave privada
   - `CUIT`: Tu CUIT
6. Hacer deploy

## Endpoints

### GET /auth
Obtiene el token y sign actuales de AFIP.

### POST /emitir_factura
Emite una factura electrónica.

## Notas

- El token y sign tienen una validez de 12 horas
- La API maneja automáticamente la renovación del token
- Los certificados deben estar en formato PEM 