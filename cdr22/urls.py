from django.urls import path, include
from . import views
from django.contrib.auth.views import LoginView, LogoutView, PasswordResetConfirmView
from django.urls import reverse_lazy

""" path = '' """
urlpatterns =[
    path ('',views.principal, name='principal'),
    path ('login', views.login_view, name='login'),
    path ('logout', LogoutView.as_view(next_page='login'), name='logout'),
    path ('olvide-password', views.olvidePassword, name='olvide-password'),
    path(
        'password-reset/confirm/<uidb64>/<token>/',
        PasswordResetConfirmView.as_view(
            template_name='registration/password_reset_confirm.html',
            success_url=reverse_lazy('login')
        ),
        name='password_reset_confirm'
    ),
    path ('testing', views.testing, name="testing"),
    path ('login-django', LoginView.as_view(template_name='login.html'), name='logindjango'),
    
    path('dashboard/home', views.home, name='home'),
    path('dashboard/mi-perfil/', views.mi_perfil, name='mi_perfil'),
    path('dashboard/categorias/', views.categorias_index, name='categorias_index'),
    path('dashboard/categorias/crear/', views.categorias_crear, name='categorias_crear'),
    path('dashboard/categorias/editar/<int:categoria_id>/', views.categorias_editar, name='categorias_editar'),
    path('dashboard/categorias/eliminar/<int:categoria_id>/', views.categorias_eliminar, name='categorias_eliminar'),
    path('dashboard/productos/', views.productos_index, name='productos_index'),
    path('dashboard/productos/crear/', views.productos_crear, name='productos_crear'),
    path('dashboard/productos/editar/<int:producto_id>/', views.productos_editar, name='productos_editar'),
    path('dashboard/productos/eliminar/<int:producto_id>/', views.productos_eliminar, name='productos_eliminar'),

    path('dashboard/pos/', views.pos, name='pos'),
    path('dashboard/ventas/', views.ventas_index, name='ventas_index'),
    path('dashboard/ventas/<int:venta_id>/', views.ventas_detalle, name='ventas_detalle'),
    path('dashboard/clientes/', views.clientes_index, name='clientes_index'),
    path('dashboard/clientes/crear/', views.clientes_crear, name='clientes_crear'),
    path('dashboard/clientes/editar/<int:cliente_id>/', views.clientes_editar, name='clientes_editar'),
    path('dashboard/clientes/eliminar/<int:cliente_id>/', views.clientes_eliminar, name='clientes_eliminar'),

    path('dashboard/proveedores/', views.proveedores_index, name='proveedores_index'),
    path('dashboard/proveedores/crear/', views.proveedores_crear, name='proveedores_crear'),
    path('dashboard/proveedores/editar/<int:proveedor_id>/', views.proveedores_editar, name='proveedores_editar'),
    path('dashboard/proveedores/eliminar/<int:proveedor_id>/', views.proveedores_eliminar, name='proveedores_eliminar'),

    path('dashboard/usuarios/', views.usuarios_index, name='usuarios_index'),
    path('dashboard/usuarios/crear/', views.usuarios_crear, name='usuarios_crear'),
    path('dashboard/configuracion/general/', views.configuracion_general, name='configuracion_general'),

    path('dashboard/compras/', views.compras_index, name='compras_index'),
    path('dashboard/compras/<int:compra_id>/', views.compras_detalle, name='compras_detalle'),
    path('dashboard/compras/crear/', views.compras_crear, name='compras_crear'),
    path('dashboard/compras/<int:compra_id>/estado/', views.compras_cambiar_estado, name='compras_cambiar_estado'),

]
