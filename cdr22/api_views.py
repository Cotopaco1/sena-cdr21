from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views import View
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.db import models
from .api_responses import error_response, success_response, validation_error_response
from .models import Compra, Orden, Producto, Cliente
from .roles import (
    PERM_MANAGE_CLIENTS,
    PERM_MANAGE_PURCHASES,
    PERM_MANAGE_SALES,
    user_can,
    user_can_any,
)
from .serializers import (
    CompraCreateSerializer,
    CompraEstadoSerializer,
    CompraReadSerializer,
    OrdenPOSCreateSerializer,
    OrdenSerializer,
    OrdenReadSerializer,
)
from .services.compras import CompraEstadoError, anular_compra, cambiar_estado_compra, crear_compra
from .services.facturas import enviar_factura_por_email, render_factura_pdf
from .services.ventas import OrdenStockError, crear_orden_pos
from .services.whatsapp import enviar_factura_por_whatsapp
import json
import logging


logger = logging.getLogger(__name__)


def _permission_error_response(request, permission):
    if not request.user.is_authenticated:
        return error_response("Autenticación requerida", status=401)

    if not user_can(request.user, permission):
        return error_response("No tienes permisos para realizar esta acción", status=403)

    return None


def _any_permission_error_response(request, permissions):
    if not request.user.is_authenticated:
        return error_response("Autenticación requerida", status=401)

    if not user_can_any(request.user, permissions):
        return error_response("No tienes permisos para realizar esta acción", status=403)

    return None

# class Authentication: 
#     def login() : 
#         return ''
#     def register() :
#         return ''

@method_decorator(csrf_exempt, name='dispatch')
class OrdenAPIView(View):
    def post(self, request) :
        permission_error = _permission_error_response(request, PERM_MANAGE_SALES)
        if permission_error:
            return permission_error

        """ Validar JSON """
        try:
            data = json.loads(request.body)
        except:
            return JsonResponse({
                "mensaje" : "Mensaje invalido, debe ser JSON"
            })
        """ Validacion de serializer """
        serializer = OrdenSerializer(data=data)
        print(serializer)
        if not serializer.is_valid():
            return JsonResponse({
                "mensaje" : "Hubo un error",
                "errores" : serializer.errors
            }, status=422)
        
        """ Datos validados, guardar orden """
        validated_data = serializer.validated_data
        order =  serializer.save()
        print(order)
        return JsonResponse({
            "mensaje" : "Creado con exito",
            "orden: " : {
                "cedula" : order.cliente.cedula if order.cliente else None,
                "precio_total" : order.precio_total,
                "estado" : order.estado,
                "metodo_pago" : order.metodo_pago,
                "id" : order.id
            }
            
        }, status=201)
    def get(self, request) : 
        permission_error = _permission_error_response(request, PERM_MANAGE_SALES)
        if permission_error:
            return permission_error

        ordenes = Orden.objects.all()
        serializer = OrdenReadSerializer(ordenes, many=True)
        return JsonResponse({
            "mensaje" : "Ordenes obtenidas con exito",
            "ordenes" : serializer.data
        })

@method_decorator(csrf_exempt, name='dispatch')
class Reportes(View):
    def get(self, request):
        permission_error = _permission_error_response(request, PERM_MANAGE_SALES)
        if permission_error:
            return permission_error

        total_ordenes = 0
        numero_de_ordenes=0
        agrupacion_pagos={}

        ordenes = Orden.objects.all()

        for orden in ordenes:
            total_ordenes +=orden.precio_total
            numero_de_ordenes +=1
            if orden.metodo_pago in agrupacion_pagos:
                agrupacion_pagos[orden.metodo_pago] +=orden.precio_total
            else:
                agrupacion_pagos[orden.metodo_pago] = orden.precio_total
            

        return JsonResponse({
            "mensaje" : "Reporte generado",
            "reporte" : {
                "total_ordenes" : total_ordenes,
                "numero_de_ordenes" : numero_de_ordenes,
                "agrupacion_pagos" : agrupacion_pagos
            }
        })

@method_decorator(csrf_exempt, name='dispatch')
class ProductoSearchAPIView(View):
    def get(self, request):
        permission_error = _any_permission_error_response(
            request,
            {PERM_MANAGE_SALES, PERM_MANAGE_PURCHASES},
        )
        if permission_error:
            return permission_error

        query = request.GET.get('q', '').strip()
        
        if not query:
            return JsonResponse({
                "mensaje": "Debe proporcionar un parámetro de búsqueda 'q'",
                "productos": []
            }, status=400)
        
        # Buscar por SKU, nombre o marca
        productos = Producto.objects.filter(
            estado='activo'
        ).filter(
            models.Q(sku__icontains=query) | 
            models.Q(nombre__icontains=query) | 
            models.Q(marca__icontains=query)
        )[:10]  # Limitar a 10 resultados
        
        resultado = []
        for producto in productos:
            resultado.append({
                'id': producto.id,
                'sku': producto.sku,
                'nombre': producto.nombre,
                'marca': producto.marca,
                'precio_venta': float(producto.precio_venta),
                'stock': producto.stock,
                'categoria': producto.categoria.nombre if producto.categoria else None,
            })
        
        return JsonResponse({
            "mensaje": "Productos encontrados",
            "productos": resultado
        })

@method_decorator(csrf_exempt, name='dispatch')
class ClienteSearchAPIView(View):
    def get(self, request):
        permission_error = _permission_error_response(request, PERM_MANAGE_CLIENTS)
        if permission_error:
            return permission_error

        cedula = request.GET.get('cedula', '').strip()
        
        if not cedula:
            return JsonResponse({
                "mensaje": "Debe proporcionar un parámetro 'cedula'",
                "cliente": None
            }, status=400)
        
        try:
            cliente = Cliente.objects.get(cedula=cedula)
            return JsonResponse({
                "mensaje": "Cliente encontrado",
                "cliente": {
                    'id': cliente.id,
                    'cedula': cliente.cedula,
                    'nombre': cliente.nombre,
                    'apellidos': cliente.apellidos,
                    'email': cliente.email,
                    'telefono': cliente.telefono,
                }
            })
        except Cliente.DoesNotExist:
            return JsonResponse({
                "mensaje": "Cliente no encontrado",
                "cliente": None
            }, status=404)

@method_decorator(csrf_exempt, name='dispatch')
class ClienteCreateAPIView(View):
    def post(self, request):
        permission_error = _permission_error_response(request, PERM_MANAGE_CLIENTS)
        if permission_error:
            return permission_error

        try:
            data = json.loads(request.body)
        except:
            return JsonResponse({
                "mensaje": "Mensaje inválido, debe ser JSON"
            }, status=400)
        
        # Validar campos requeridos
        cedula = data.get('cedula', '').strip()
        nombre = data.get('nombre', '').strip()
        apellidos = data.get('apellidos', '').strip()
        
        if not cedula or not nombre or not apellidos:
            return JsonResponse({
                "mensaje": "Los campos cedula, nombre y apellidos son requeridos",
                "errores": {
                    "cedula": "Requerido" if not cedula else "",
                    "nombre": "Requerido" if not nombre else "",
                    "apellidos": "Requerido" if not apellidos else "",
                }
            }, status=422)
        
        # Verificar si ya existe
        if Cliente.objects.filter(cedula=cedula).exists():
            return JsonResponse({
                "mensaje": "Ya existe un cliente con esta cédula",
            }, status=422)
        
        # Crear cliente
        cliente = Cliente.objects.create(
            cedula=cedula,
            nombre=nombre,
            apellidos=apellidos,
            email=data.get('email', ''),
            telefono=data.get('telefono', '')
        )
        
        return JsonResponse({
            "mensaje": "Cliente creado exitosamente",
            "cliente": {
                'id': cliente.id,
                'cedula': cliente.cedula,
                'nombre': cliente.nombre,
                'apellidos': cliente.apellidos,
                'email': cliente.email,
                'telefono': cliente.telefono,
            }
        }, status=201)

@method_decorator(csrf_exempt, name='dispatch')
class OrdenCreateAPIView(View):
    def post(self, request):
        permission_error = _permission_error_response(request, PERM_MANAGE_SALES)
        if permission_error:
            return permission_error

        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return error_response("Mensaje inválido, debe ser JSON", status=400)

        serializer = OrdenPOSCreateSerializer(data=data)
        if not serializer.is_valid():
            return validation_error_response(serializer.errors)

        try:
            orden = crear_orden_pos(serializer.validated_data)
        except OrdenStockError as e:
            return validation_error_response(e.errores)

        base_url = request.build_absolute_uri('/')
        factura_pdf_url = request.build_absolute_uri(
            f'/api/ordenes/{orden.id}/factura/pdf/'
        )
        email_enviado = False
        email_error = None
        whatsapp_enviado = False
        whatsapp_error = None

        if serializer.validated_data.get('enviar_factura_email'):
            try:
                enviar_factura_por_email(orden, base_url=base_url)
                email_enviado = True
            except Exception as e:
                logger.exception("No se pudo enviar la factura por email para la orden %s", orden.id)
                email_error = str(e)

        if serializer.validated_data.get('enviar_factura_whatsapp'):
            try:
                enviar_factura_por_whatsapp(orden, base_url=base_url)
                whatsapp_enviado = True
            except Exception as e:
                logger.exception("No se pudo enviar la factura por WhatsApp para la orden %s", orden.id)
                whatsapp_error = str(e)

        data = {
            "orden": {
                'id': orden.id,
                'factura_numero': orden.factura.numero,
                'factura_pdf_url': factura_pdf_url if serializer.validated_data.get('generar_factura_pdf') else None,
                'email_enviado': email_enviado,
                'email_error': email_error,
                'whatsapp_enviado': whatsapp_enviado,
                'whatsapp_error': whatsapp_error,
                'cliente': {
                    'cedula': orden.cliente.cedula,
                    'nombre': orden.cliente.nombre,
                    'apellidos': orden.cliente.apellidos,
                    'email': orden.cliente.email,
                },
                'subtotal': str(orden.subtotal),
                'impuesto': str(orden.impuesto),
                'total': str(orden.precio_total),
                'estado': orden.estado,
                'fecha': orden.created_at.isoformat()
            }
        }

        return success_response("Orden creada exitosamente", data=data, status=201)


@method_decorator(csrf_exempt, name='dispatch')
class FacturaPDFAPIView(View):
    def get(self, request, orden_id):
        permission_error = _permission_error_response(request, PERM_MANAGE_SALES)
        if permission_error:
            return permission_error

        try:
            orden = Orden.objects.select_related('cliente', 'factura').prefetch_related('items').get(id=orden_id)
        except Orden.DoesNotExist:
            orden = None

        if not orden or not orden.factura:
            return error_response("Factura no encontrada", status=404)

        pdf = render_factura_pdf(orden, base_url=request.build_absolute_uri('/'))
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="factura-{orden.factura.numero}.pdf"'
        return response

@method_decorator(csrf_exempt, name='dispatch')
class ComprasAPIView(View):
    def get(self, request):
        permission_error = _permission_error_response(request, PERM_MANAGE_PURCHASES)
        if permission_error:
            return permission_error

        compras = Compra.objects.select_related('proveedor').all()
        serializer = CompraReadSerializer(compras, many=True)
        return success_response(
            "Compras obtenidas con éxito",
            data={"compras": serializer.data}
        )

    def post(self, request):
        permission_error = _permission_error_response(request, PERM_MANAGE_PURCHASES)
        if permission_error:
            return permission_error

        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return error_response("Mensaje inválido, debe ser JSON", status=400)

        serializer = CompraCreateSerializer(data=data)
        if not serializer.is_valid():
            return validation_error_response(serializer.errors)

        compra = crear_compra(serializer.validated_data)
        read_serializer = CompraReadSerializer(compra)
        return success_response(
            "Compra creada exitosamente",
            data={"compra": read_serializer.data},
            status=201
        )

@method_decorator(csrf_exempt, name='dispatch')
class CompraEstadoAPIView(View):
    def patch(self, request, compra_id):
        permission_error = _permission_error_response(request, PERM_MANAGE_PURCHASES)
        if permission_error:
            return permission_error

        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return error_response("Mensaje inválido, debe ser JSON", status=400)

        try:
            compra = Compra.objects.get(id=compra_id)
        except Compra.DoesNotExist:
            return error_response("Compra no encontrada", status=404)

        serializer = CompraEstadoSerializer(data=data)
        if not serializer.is_valid():
            return validation_error_response(serializer.errors)

        try:
            if serializer.validated_data['estado'] == 'anulada':
                compra = anular_compra(
                    compra,
                    motivo=serializer.validated_data.get('motivo_anulacion', '')
                )
            else:
                compra = cambiar_estado_compra(compra, serializer.validated_data['estado'])
        except CompraEstadoError as e:
            return validation_error_response(e.errores)

        read_serializer = CompraReadSerializer(compra)
        return success_response(
            "Estado de compra actualizado correctamente",
            data={"compra": read_serializer.data}
        )
