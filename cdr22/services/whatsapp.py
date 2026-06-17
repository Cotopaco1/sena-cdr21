from django.conf import settings
import requests

from cdr22.services.configuracion import get_configuracion_sistema
from cdr22.services.facturas import render_factura_pdf


class WhatsAppConfigError(Exception):
    pass


class WhatsAppAPIError(Exception):
    pass


def get_whatsapp_estado():
    configuracion = get_configuracion_sistema()
    env_configurado = all([
        settings.WHATSAPP_ACCESS_TOKEN,
        settings.WHATSAPP_PHONE_NUMBER_ID,
    ])
    plantilla_configurada = bool(
        configuracion.whatsapp_template_factura
        and configuracion.whatsapp_template_language
    )

    return {
        'habilitado': configuracion.whatsapp_habilitado,
        'env_configurado': env_configurado,
        'plantilla_configurada': plantilla_configurada,
        'listo_para_enviar': (
            configuracion.whatsapp_habilitado
            and env_configurado
            and plantilla_configurada
        ),
    }


def normalizar_telefono_colombia(numero):
    digitos = ''.join(caracter for caracter in str(numero or '') if caracter.isdigit())

    if len(digitos) == 10:
        return f'57{digitos}'

    if len(digitos) == 12 and digitos.startswith('57'):
        return digitos

    return None


def _graph_api_url(path):
    version = settings.WHATSAPP_GRAPH_API_VERSION.strip().strip('/')
    return f'https://graph.facebook.com/{version}/{path.lstrip("/")}'


def _headers():
    return {
        'Authorization': f'Bearer {settings.WHATSAPP_ACCESS_TOKEN}',
    }


def _raise_for_meta_error(response):
    if response.ok:
        return

    try:
        payload = response.json()
    except ValueError:
        payload = {'error': {'message': response.text}}

    error = payload.get('error', {})
    message = error.get('message') or 'Meta rechazó la solicitud.'
    code = error.get('code')
    details = f' Código: {code}.' if code else ''
    raise WhatsAppAPIError(f'{message}{details}')


def _validar_configuracion_whatsapp(configuracion):
    estado = get_whatsapp_estado()

    if not estado['listo_para_enviar']:
        raise WhatsAppConfigError('WhatsApp no está completamente configurado.')

    if not configuracion.whatsapp_template_factura:
        raise WhatsAppConfigError('Falta configurar la plantilla de factura.')

    return estado


def subir_factura_pdf(orden, base_url=None):
    pdf = render_factura_pdf(orden, base_url=base_url)
    url = _graph_api_url(f'{settings.WHATSAPP_PHONE_NUMBER_ID}/media')

    response = requests.post(
        url,
        headers=_headers(),
        data={
            'messaging_product': 'whatsapp',
            'type': 'application/pdf',
        },
        files={
            'file': (
                f'factura-{orden.factura.numero}.pdf',
                pdf,
                'application/pdf',
            ),
        },
        timeout=30,
    )
    _raise_for_meta_error(response)

    media_id = response.json().get('id')
    if not media_id:
        raise WhatsAppAPIError('Meta no retornó el identificador del documento.')

    return media_id


def enviar_factura_por_whatsapp(orden, base_url=None):
    configuracion = get_configuracion_sistema()
    _validar_configuracion_whatsapp(configuracion)

    telefono = normalizar_telefono_colombia(orden.cliente.telefono if orden.cliente else '')
    if not telefono:
        raise WhatsAppConfigError('El cliente no tiene un teléfono válido para WhatsApp.')

    media_id = subir_factura_pdf(orden, base_url=base_url)
    url = _graph_api_url(f'{settings.WHATSAPP_PHONE_NUMBER_ID}/messages')
    payload = {
        'messaging_product': 'whatsapp',
        'to': telefono,
        'type': 'template',
        'template': {
            'name': configuracion.whatsapp_template_factura,
            'language': {
                'code': configuracion.whatsapp_template_language,
            },
            'components': [
                {
                    'type': 'header',
                    'parameters': [
                        {
                            'type': 'document',
                            'document': {
                                'id': media_id,
                                'filename': f'factura-{orden.factura.numero}.pdf',
                            },
                        },
                    ],
                },
                {
                    'type': 'body',
                    'parameters': [
                        {
                            'type': 'text',
                            'text': configuracion.nombre_empresa,
                        },
                    ],
                },
            ],
        },
    }

    response = requests.post(
        url,
        headers={
            **_headers(),
            'Content-Type': 'application/json',
        },
        json=payload,
        timeout=30,
    )
    _raise_for_meta_error(response)

    return response.json()
