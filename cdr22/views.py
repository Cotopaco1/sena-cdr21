from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm, PasswordChangeForm
from django.contrib.auth import authenticate, login as auth_login
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth.models import Group, User
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.contrib import messages
from django.db import IntegrityError
from django.db.models import Avg, Count, F, Sum
from django.utils import timezone
from functools import wraps
import secrets
from cdr22.forms import ConfiguracionSistemaForm, PerfilUsuarioForm, UsuarioCreateForm
from cdr22.models import Producto, Categoria, Cliente, Compra, Orden, Proveedor
from cdr22.roles import (
    PERM_MANAGE_CLIENTS,
    PERM_MANAGE_INVENTORY,
    PERM_MANAGE_PURCHASES,
    PERM_MANAGE_SALES,
    PERM_MANAGE_SETTINGS,
    PERM_MANAGE_USERS,
    ROLE_NAMES,
    user_can,
)
from cdr22.serializers import CompraCreateSerializer
from cdr22.services.configuracion import get_configuracion_sistema
from cdr22.services.compras import CompraEstadoError, anular_compra, cambiar_estado_compra, crear_compra
import json


def _compra_payload_from_post(post_data):
    items = []
    producto_ids = post_data.getlist('producto')
    cantidades = post_data.getlist('cantidad')
    costos = post_data.getlist('costo_unitario')

    for producto_id, cantidad, costo_unitario in zip(producto_ids, cantidades, costos):
        if not producto_id:
            continue

        items.append({
            'producto_id': producto_id,
            'cantidad': cantidad,
            'costo_unitario': costo_unitario,
        })

    return {
        'proveedor_id': post_data.get('proveedor') or None,
        'proveedor_nombre': post_data.get('proveedor_nombre', '').strip(),
        'numero_factura': post_data.get('numero_factura', '').strip(),
        'fecha_compra': post_data.get('fecha_compra'),
        'estado': post_data.get('estado', 'borrador'),
        'metodo_pago': post_data.get('metodo_pago', ''),
        'impuesto': post_data.get('impuesto') or '0',
        'observaciones': post_data.get('observaciones', '').strip(),
        'items': items,
    }

def _permission_required(permission):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if user_can(request.user, permission):
                return view_func(request, *args, **kwargs)

            messages.error(request, 'No tienes permisos para acceder a esta sección.')
            return redirect('home')

        return wrapped

    return decorator

def _ensure_roles():
    for role_name in ROLE_NAMES:
        Group.objects.get_or_create(name=role_name)

def _send_password_setup_email(request, user):
    reset_form = PasswordResetForm({'email': user.email})
    if reset_form.is_valid():
        reset_form.save(
            request=request,
            use_https=request.is_secure(),
            email_template_name='registration/password_setup_email.html',
            subject_template_name='registration/password_setup_subject.txt',
        )

def _user_role_names(user):
    roles = list(user.groups.order_by('name').values_list('name', flat=True))
    if user.is_superuser and 'Superusuario' not in roles:
        roles.insert(0, 'Superusuario')
    return roles

def principal (request):
    return render(request, 'landing.html')

""" Auth Views """
def login_view(request):
    if request.method == 'POST':
        # Si viene JSON (desde fetch)
           if request.content_type == 'application/json':
               data = json.loads(request.body)
               print(data)  # Aquí ves los datos
               username = data.get('user')  # o 'username' según lo que envíes
               password = data.get('password')

               user = authenticate(request, username=username, password=password)
               if user is not None:
                   auth_login(request, user)
                   return JsonResponse({"message": "Login exitoso"})
               else:
                   return JsonResponse({"message": "Credenciales inválidas"}, status=422)

           # Si viene formulario tradicional
           else:
               form = AuthenticationForm(request, data=request.POST)
               if form.is_valid():
                   user = form.get_user()
                   auth_login(request, user)
                   return redirect('home')
               else:
                   return JsonResponse({"message": "Credenciales inválidas"}, status=422)
    return render(request, 'invitado/login.html')   

def olvidePassword(request):
    return render(request, 'invitado/olvide-password.html')


""" Dashboard Views """
@login_required(login_url='login') 
def home(request):
    hoy = timezone.localdate()

    ventas_hoy = Orden.objects.exclude(estado='cancelada').filter(created_at__date=hoy)
    ventas_resumen = ventas_hoy.aggregate(
        total=Sum('precio_total'),
        promedio=Avg('precio_total'),
    )

    stock_bajo_queryset = Producto.objects.filter(
        estado='activo',
        stock__lte=F('stock_minimo'),
    )

    context = {
        'hoy': hoy,
        'ventas_hoy_total': ventas_resumen['total'] or 0,
        'ventas_hoy_count': ventas_hoy.count(),
        'ticket_promedio': ventas_resumen['promedio'] or 0,
        'compras_en_espera_count': Compra.objects.filter(estado='en_espera').count(),
        'compras_stock_pendiente_count': Compra.objects.exclude(estado='anulada').filter(stock_aplicado=False).count(),
        'productos_activos_count': Producto.objects.filter(estado='activo').count(),
        'productos_sin_stock_count': Producto.objects.filter(estado='activo', stock=0).count(),
        'productos_stock_bajo_count': stock_bajo_queryset.count(),
        'productos_sin_categoria_count': Producto.objects.filter(estado='activo', categoria__isnull=True).count(),
        'stock_critico': stock_bajo_queryset.select_related('categoria').order_by('stock', 'nombre')[:5],
        'ultimas_ventas': Orden.objects.select_related('cliente', 'factura').order_by('-created_at')[:5],
        'ultimas_compras': Compra.objects.select_related('proveedor').order_by('-fecha_compra', '-created_at')[:5],
    }

    return render(request, 'dashboard/home.html', context)

@login_required(login_url='login')
def mi_perfil(request):
    user = request.user

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'profile':
            profile_form = PerfilUsuarioForm(request.POST, instance=user)
            password_form = PasswordChangeForm(user)

            if profile_form.is_valid():
                profile_form.save()
                messages.success(request, 'Perfil actualizado correctamente.')
                return redirect('mi_perfil')

            messages.error(request, 'No se pudo actualizar el perfil. Revise los campos marcados.')
        elif action == 'password':
            profile_form = PerfilUsuarioForm(instance=user)
            password_form = PasswordChangeForm(user, request.POST)

            if password_form.is_valid():
                updated_user = password_form.save()
                update_session_auth_hash(request, updated_user)
                messages.success(request, 'Contraseña actualizada correctamente.')
                return redirect('mi_perfil')

            messages.error(request, 'No se pudo actualizar la contraseña. Revise los campos marcados.')
        else:
            profile_form = PerfilUsuarioForm(instance=user)
            password_form = PasswordChangeForm(user)
            messages.error(request, 'Acción no válida.')
    else:
        profile_form = PerfilUsuarioForm(instance=user)
        password_form = PasswordChangeForm(user)

    return render(request, 'dashboard/perfil/mi_perfil.html', {
        'profile_form': profile_form,
        'password_form': password_form,
        'role_names': _user_role_names(user),
    })

def testing(request):
    return render(request, 'testing.html')

""" Productos Views """
@login_required(login_url='login')
@_permission_required(PERM_MANAGE_INVENTORY)
def categorias_index(request):
    categorias_list = Categoria.objects.annotate(productos_count=Count('productos')).order_by('nombre')
    paginator = Paginator(categorias_list, 10)
    page_number = request.GET.get('page')
    categorias = paginator.get_page(page_number)

    return render(request, 'dashboard/categorias/index.html', {'categorias': categorias})

@login_required(login_url='login')
@_permission_required(PERM_MANAGE_INVENTORY)
def categorias_crear(request):
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        descripcion = request.POST.get('descripcion', '').strip()

        try:
            Categoria.objects.create(
                nombre=nombre,
                descripcion=descripcion or None,
            )
            messages.success(request, 'Categoría creada correctamente.')
            return redirect('categorias_index')
        except IntegrityError:
            return render(request, 'dashboard/categorias/crear.html', {
                'error': 'Ya existe una categoría con ese nombre.',
                'categoria': {
                    'nombre': nombre,
                    'descripcion': descripcion,
                },
            })

    return render(request, 'dashboard/categorias/crear.html')

@login_required(login_url='login')
@_permission_required(PERM_MANAGE_INVENTORY)
def categorias_editar(request, categoria_id):
    categoria = get_object_or_404(Categoria, id=categoria_id)

    if request.method == 'POST':
        categoria.nombre = request.POST.get('nombre', '').strip()
        categoria.descripcion = request.POST.get('descripcion', '').strip() or None

        try:
            categoria.save()
            messages.success(request, 'Categoría actualizada correctamente.')
            return redirect('categorias_index')
        except IntegrityError:
            return render(request, 'dashboard/categorias/editar.html', {
                'categoria': categoria,
                'error': 'Ya existe una categoría con ese nombre.',
            })

    return render(request, 'dashboard/categorias/editar.html', {'categoria': categoria})

@login_required(login_url='login')
@_permission_required(PERM_MANAGE_INVENTORY)
def categorias_eliminar(request, categoria_id):
    categoria = get_object_or_404(
        Categoria.objects.annotate(productos_count=Count('productos')),
        id=categoria_id
    )

    if request.method == 'POST':
        categoria.delete()
        messages.success(request, 'Categoría eliminada correctamente.')
        return redirect('categorias_index')

    return render(request, 'dashboard/categorias/eliminar.html', {
        'categoria': categoria
    })

@login_required(login_url='login')
@_permission_required(PERM_MANAGE_INVENTORY)
def productos_index(request):
    productos_list = Producto.objects.all()
    paginator = Paginator(productos_list, 10)
    page_number = request.GET.get('page')
    productos = paginator.get_page(page_number)
    
    return render(request, 'dashboard/productos/index.html', {'productos': productos})

@login_required(login_url='login')
@_permission_required(PERM_MANAGE_INVENTORY)
def productos_crear(request):
    if request.method == 'POST':
        sku = request.POST.get('sku')
        nombre = request.POST.get('nombre')
        descripcion = request.POST.get('descripcion')
        categoria_id = request.POST.get('categoria')
        marca = request.POST.get('marca')
        precio_costo = request.POST.get('precio_costo')
        precio_venta = request.POST.get('precio_venta')
        garantia_meses = request.POST.get('garantia_meses')
        stock_minimo = request.POST.get('stock_minimo') or 5
        estado = request.POST.get('estado')
        
        try:
            categoria = Categoria.objects.get(id=categoria_id)
            
            Producto.objects.create(
                sku=sku,
                nombre=nombre,
                descripcion=descripcion,
                categoria=categoria,
                marca=marca,
                precio_costo=precio_costo,
                precio_venta=precio_venta,
                garantia_meses=garantia_meses,
                stock_minimo=stock_minimo,
                estado=estado
            )
            
            return redirect('productos_index')
        except Categoria.DoesNotExist:
            return render(request, 'dashboard/productos/crear.html', {
                'categorias': Categoria.objects.all(),
                'error': 'Categoría no válida'
            })
    
    categorias = Categoria.objects.all()
    return render(request, 'dashboard/productos/crear.html', {'categorias': categorias})

@login_required(login_url='login')
@_permission_required(PERM_MANAGE_INVENTORY)
def productos_editar(request, producto_id):
    producto = get_object_or_404(Producto, id=producto_id)
    
    if request.method == 'POST':
        sku = request.POST.get('sku')
        nombre = request.POST.get('nombre')
        descripcion = request.POST.get('descripcion')
        categoria_id = request.POST.get('categoria')
        marca = request.POST.get('marca')
        precio_costo = request.POST.get('precio_costo')
        precio_venta = request.POST.get('precio_venta')
        garantia_meses = request.POST.get('garantia_meses')
        stock_minimo = request.POST.get('stock_minimo') or 5
        estado = request.POST.get('estado')
        
        try:
            categoria = Categoria.objects.get(id=categoria_id)
            
            # Actualizar el producto
            producto.sku = sku
            producto.nombre = nombre
            producto.descripcion = descripcion
            producto.categoria = categoria
            producto.marca = marca
            producto.precio_costo = precio_costo
            producto.precio_venta = precio_venta
            producto.garantia_meses = garantia_meses
            producto.stock_minimo = stock_minimo
            producto.estado = estado
            producto.save()
            
            return redirect('productos_index')
        except Categoria.DoesNotExist:
            return render(request, 'dashboard/productos/editar.html', {
                'producto': producto,
                'categorias': Categoria.objects.all(),
                'error': 'Categoría no válida'
            })
    
    categorias = Categoria.objects.all()
    return render(request, 'dashboard/productos/editar.html', {
        'producto': producto,
        'categorias': categorias
    })

@login_required(login_url='login')
@_permission_required(PERM_MANAGE_INVENTORY)
def productos_eliminar(request, producto_id):
    producto = get_object_or_404(Producto, id=producto_id)
    
    if request.method == 'POST':
        # Guardar información del producto para el mensaje
        producto_nombre = producto.nombre
        producto_sku = producto.sku
        
        # Eliminar el producto
        producto.delete()
        
        return redirect('productos_index')
    
    # Si es GET, mostrar página de confirmación
    return render(request, 'dashboard/productos/eliminar.html', {
        'producto': producto
    })

@login_required(login_url='login')
@_permission_required(PERM_MANAGE_SALES)
def pos(request):
    return render(request, 'dashboard/pos/index.html')

@login_required(login_url='login')
@_permission_required(PERM_MANAGE_SALES)
def ventas_index(request):
    ventas_list = Orden.objects.select_related('cliente', 'factura').prefetch_related('items').all()
    paginator = Paginator(ventas_list, 10)
    page_number = request.GET.get('page')
    ventas = paginator.get_page(page_number)

    return render(request, 'dashboard/ventas/index.html', {'ventas': ventas})

@login_required(login_url='login')
@_permission_required(PERM_MANAGE_SALES)
def ventas_detalle(request, venta_id):
    venta = get_object_or_404(
        Orden.objects.select_related('cliente', 'factura').prefetch_related('items'),
        id=venta_id
    )

    return render(request, 'dashboard/ventas/detalle.html', {'venta': venta})

@login_required(login_url='login')
@_permission_required(PERM_MANAGE_CLIENTS)
def clientes_index(request):
    clientes_list = Cliente.objects.all()
    paginator = Paginator(clientes_list, 10)
    page_number = request.GET.get('page')
    clientes = paginator.get_page(page_number)
    
    return render(request, 'dashboard/clientes/index.html', {'clientes': clientes})

@login_required(login_url='login')
@_permission_required(PERM_MANAGE_CLIENTS)
def clientes_crear(request):
    if request.method == 'POST':
        cedula = request.POST.get('cedula')
        nombre = request.POST.get('nombre')
        apellidos = request.POST.get('apellidos')
        email = request.POST.get('email', '')
        telefono = request.POST.get('telefono', '')
        
        try:
            cliente = Cliente.objects.create(
                cedula=cedula,
                nombre=nombre,
                apellidos=apellidos,
                email=email,
                telefono=telefono
            )
            return redirect('clientes_index')
        except Exception as e:
            return render(request, 'dashboard/clientes/crear.html', {
                'error': str(e)
            })
    
    return render(request, 'dashboard/clientes/crear.html')

@login_required(login_url='login')
@_permission_required(PERM_MANAGE_CLIENTS)
def clientes_editar(request, cliente_id):
    cliente = get_object_or_404(Cliente, id=cliente_id)
    
    if request.method == 'POST':
        cedula = request.POST.get('cedula')
        nombre = request.POST.get('nombre')
        apellidos = request.POST.get('apellidos')
        email = request.POST.get('email', '')
        telefono = request.POST.get('telefono', '')
        
        try:
            cliente.cedula = cedula
            cliente.nombre = nombre
            cliente.apellidos = apellidos
            cliente.email = email
            cliente.telefono = telefono
            cliente.save()
            
            return redirect('clientes_index')
        except Exception as e:
            return render(request, 'dashboard/clientes/editar.html', {
                'cliente': cliente,
                'error': str(e)
            })
    
    return render(request, 'dashboard/clientes/editar.html', {
        'cliente': cliente
    })

@login_required(login_url='login')
@_permission_required(PERM_MANAGE_CLIENTS)
def clientes_eliminar(request, cliente_id):
    cliente = get_object_or_404(Cliente, id=cliente_id)
    
    if request.method == 'POST':
        cliente.delete()
        return redirect('clientes_index')
    
    return render(request, 'dashboard/clientes/eliminar.html', {
        'cliente': cliente
    })

@login_required(login_url='login')
@_permission_required(PERM_MANAGE_PURCHASES)
def proveedores_index(request):
    proveedores_list = Proveedor.objects.annotate(compras_count=Count('compras')).order_by('nombre')
    paginator = Paginator(proveedores_list, 10)
    page_number = request.GET.get('page')
    proveedores = paginator.get_page(page_number)

    return render(request, 'dashboard/proveedores/index.html', {'proveedores': proveedores})

@login_required(login_url='login')
@_permission_required(PERM_MANAGE_PURCHASES)
def proveedores_crear(request):
    if request.method == 'POST':
        Proveedor.objects.create(
            nombre=request.POST.get('nombre', '').strip(),
            documento=request.POST.get('documento', '').strip() or None,
            telefono=request.POST.get('telefono', '').strip() or None,
            email=request.POST.get('email', '').strip() or None,
            direccion=request.POST.get('direccion', '').strip() or None,
        )
        messages.success(request, 'Proveedor creado correctamente.')
        return redirect('proveedores_index')

    return render(request, 'dashboard/proveedores/crear.html')

@login_required(login_url='login')
@_permission_required(PERM_MANAGE_PURCHASES)
def proveedores_editar(request, proveedor_id):
    proveedor = get_object_or_404(Proveedor, id=proveedor_id)

    if request.method == 'POST':
        proveedor.nombre = request.POST.get('nombre', '').strip()
        proveedor.documento = request.POST.get('documento', '').strip() or None
        proveedor.telefono = request.POST.get('telefono', '').strip() or None
        proveedor.email = request.POST.get('email', '').strip() or None
        proveedor.direccion = request.POST.get('direccion', '').strip() or None
        proveedor.save()

        messages.success(request, 'Proveedor actualizado correctamente.')
        return redirect('proveedores_index')

    return render(request, 'dashboard/proveedores/editar.html', {'proveedor': proveedor})

@login_required(login_url='login')
@_permission_required(PERM_MANAGE_PURCHASES)
def proveedores_eliminar(request, proveedor_id):
    proveedor = get_object_or_404(
        Proveedor.objects.annotate(compras_count=Count('compras')),
        id=proveedor_id
    )

    if request.method == 'POST':
        proveedor.delete()
        messages.success(request, 'Proveedor eliminado correctamente.')
        return redirect('proveedores_index')

    return render(request, 'dashboard/proveedores/eliminar.html', {
        'proveedor': proveedor
    })

@login_required(login_url='login')
@_permission_required(PERM_MANAGE_USERS)
def usuarios_index(request):
    usuarios_list = User.objects.prefetch_related('groups').order_by('username')
    paginator = Paginator(usuarios_list, 10)
    page_number = request.GET.get('page')
    usuarios = paginator.get_page(page_number)

    return render(request, 'dashboard/usuarios/index.html', {'usuarios': usuarios})

@login_required(login_url='login')
@_permission_required(PERM_MANAGE_USERS)
def usuarios_crear(request):
    _ensure_roles()

    if request.method == 'POST':
        form = UsuarioCreateForm(request.POST)
        if form.is_valid():
            user = User(
                username=form.cleaned_data['username'],
                email=form.cleaned_data['email'],
                first_name=form.cleaned_data['first_name'],
                last_name=form.cleaned_data['last_name'],
                is_active=form.cleaned_data['is_active'],
            )

            if form.cleaned_data['password_mode'] == 'manual':
                user.set_password(form.cleaned_data['password1'])
            else:
                user.set_password(secrets.token_urlsafe(24))

            user.save()
            user.groups.set([form.cleaned_data['role']])

            if form.cleaned_data['password_mode'] == 'email':
                _send_password_setup_email(request, user)
                messages.success(request, 'Usuario creado. Se generó el correo para configurar contraseña.')
            else:
                messages.success(request, 'Usuario creado correctamente.')

            return redirect('usuarios_index')
    else:
        form = UsuarioCreateForm(initial={'password_mode': 'email', 'is_active': True})

    return render(request, 'dashboard/usuarios/crear.html', {'form': form})

@login_required(login_url='login')
@_permission_required(PERM_MANAGE_SETTINGS)
def configuracion_general(request):
    configuracion = get_configuracion_sistema()

    if request.method == 'POST':
        form = ConfiguracionSistemaForm(request.POST, request.FILES, instance=configuracion)
        if form.is_valid():
            form.save()
            messages.success(request, 'Configuración actualizada correctamente.')
            return redirect('configuracion_general')
        messages.error(request, 'No se pudo guardar la configuración. Revise los campos marcados.')
    else:
        form = ConfiguracionSistemaForm(instance=configuracion)

    return render(request, 'dashboard/configuracion/general.html', {'form': form})

@login_required(login_url='login')
@_permission_required(PERM_MANAGE_PURCHASES)
def compras_index(request):
    compras_list = Compra.objects.select_related('proveedor').prefetch_related('items').all()
    paginator = Paginator(compras_list, 10)
    page_number = request.GET.get('page')
    compras = paginator.get_page(page_number)

    return render(request, 'dashboard/compras/index.html', {'compras': compras})

@login_required(login_url='login')
@_permission_required(PERM_MANAGE_PURCHASES)
def compras_detalle(request, compra_id):
    compra = get_object_or_404(
        Compra.objects.select_related('proveedor').prefetch_related('items__producto'),
        id=compra_id
    )

    return render(request, 'dashboard/compras/detalle.html', {'compra': compra})

@login_required(login_url='login')
@_permission_required(PERM_MANAGE_PURCHASES)
def compras_crear(request):
    productos = Producto.objects.filter(estado='activo').order_by('nombre')
    proveedores = Proveedor.objects.all()

    if request.method == 'POST':
        payload = _compra_payload_from_post(request.POST)
        serializer = CompraCreateSerializer(data=payload)

        if serializer.is_valid():
            crear_compra(serializer.validated_data)
            return redirect('compras_index')

        return render(request, 'dashboard/compras/crear.html', {
            'productos': productos,
            'proveedores': proveedores,
            'error': 'Hay errores en el formulario',
            'form_errors': serializer.errors,
        })

    return render(request, 'dashboard/compras/crear.html', {
        'productos': productos,
        'proveedores': proveedores,
    })

@login_required(login_url='login')
@_permission_required(PERM_MANAGE_PURCHASES)
def compras_cambiar_estado(request, compra_id):
    compra = get_object_or_404(Compra, id=compra_id)

    if request.method != 'POST':
        return redirect('compras_index')

    nuevo_estado = request.POST.get('estado')
    motivo_anulacion = request.POST.get('motivo_anulacion', '').strip()

    try:
        if nuevo_estado == 'anulada':
            anular_compra(compra, motivo=motivo_anulacion)
        else:
            cambiar_estado_compra(compra, nuevo_estado)
        messages.success(request, 'Estado de la compra actualizado correctamente.')
    except CompraEstadoError as e:
        primer_error = next(iter(e.errores.values()))[0]
        messages.error(request, primer_error)

    return redirect('compras_index')
