from django.db import models
from django.utils import timezone

# ============================================
# CONFIGURACIÓN
# ============================================

class ConfiguracionSistema(models.Model):
    MONEDA_CHOICES = [
        ('COP', 'COP - Peso colombiano'),
    ]

    nombre_empresa = models.CharField(max_length=150, default='Las Motos')
    nit_empresa = models.CharField(max_length=50, blank=True, null=True)
    direccion_empresa = models.CharField(max_length=255, blank=True, null=True)
    ciudad_empresa = models.CharField(max_length=100, blank=True, null=True)
    pais_empresa = models.CharField(max_length=100, blank=True, null=True, default='Colombia')
    telefono_empresa = models.CharField(max_length=30, blank=True, null=True)
    email_empresa = models.EmailField(blank=True, null=True)
    logo = models.ImageField(upload_to='empresa/logos/', blank=True, null=True)
    prefijo_factura = models.CharField(max_length=10, default='FAC')
    siguiente_numero_factura = models.PositiveIntegerField(default=1)
    impuesto_porcentaje = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    moneda = models.CharField(max_length=10, choices=MONEDA_CHOICES, default='COP')
    whatsapp_habilitado = models.BooleanField(default=False)
    whatsapp_template_factura = models.CharField(max_length=100, blank=True, null=True)
    whatsapp_template_language = models.CharField(max_length=10, default='es_CO')
    whatsapp_numero_prueba = models.CharField(max_length=20, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'configuracion_sistema'
        verbose_name = 'Configuración del sistema'
        verbose_name_plural = 'Configuración del sistema'

    def __str__(self):
        return self.nombre_empresa

# ============================================
# CLIENTES
# ============================================

class Cliente(models.Model):
    cedula = models.CharField(max_length=20, unique=True, help_text="Cédula de identidad")
    nombre = models.CharField(max_length=100)
    apellidos = models.CharField(max_length=100)
    email = models.EmailField(blank=True, null=True)
    telefono = models.CharField(max_length=20, blank=True, null=True)
    
    # Auditoría
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'clientes'
        verbose_name_plural = 'Clientes'
        ordering = ['nombre']
    
    def __str__(self):
        return f"{self.nombre} {self.apellidos} - {self.cedula}"

# ============================================
# PRODUCTOS
# ============================================

class Categoria(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'categorias'
        verbose_name_plural = 'Categorías'
        ordering = ['nombre']
    
    def __str__(self):
        return self.nombre

class Producto(models.Model):
    ESTADO_CHOICES = [
        ('activo', 'Activo'),
        ('inactivo', 'Inactivo'),
        ('descontinuado', 'Descontinuado'),
    ]
    
    # Información básica
    nombre = models.CharField(max_length=150)
    descripcion = models.TextField()
    sku = models.CharField(max_length=50, unique=True, help_text="Código único del repuesto")
    
    # Categoría
    categoria = models.ForeignKey(Categoria, on_delete=models.SET_NULL, null=True, related_name='productos')
    
    # Precios
    precio_costo = models.DecimalField(max_digits=15, decimal_places=2, help_text="Costo para el taller")
    precio_venta = models.DecimalField(max_digits=15, decimal_places=2, help_text="Precio al cliente")
    
    # Stock
    stock = models.PositiveIntegerField(default=0, help_text="Cantidad disponible")
    stock_minimo = models.PositiveIntegerField(default=5)
    
    # Detalles
    marca = models.CharField(max_length=100, help_text="Fabricante del repuesto")
    garantia_meses = models.PositiveIntegerField(default=12, help_text="Meses de garantía")
    
    # Estado
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='activo')
    
    # Auditoría
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'productos'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.nombre} - {self.sku}"
    
    def margen_ganancia(self):
        """Calcula el margen de ganancia en porcentaje"""
        if self.precio_costo > 0:
            return ((self.precio_venta - self.precio_costo) / self.precio_costo) * 100
        return 0

# ============================================
# FACTURAS
# ============================================

class Factura(models.Model):
    ESTADO_CHOICES = [
        ('emitida', 'Emitida'),
        ('pagada', 'Pagada'),
        ('anulada', 'Anulada'),
        ('pendiente', 'Pendiente de pago'),
    ]
    
    numero = models.CharField(max_length=50, unique=True, help_text="Número de factura")
    cliente = models.ForeignKey(Cliente, on_delete=models.SET_NULL, null=True, related_name='facturas')
    
    subtotal = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    impuesto = models.DecimalField(max_digits=15, decimal_places=2, default=0, help_text="Impuesto (IVA, etc.)")
    total = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    metodo_pago = models.CharField(max_length=100, blank=True, null=True)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='emitida')
    
    fecha_emision = models.DateTimeField(auto_now_add=True)
    fecha_vencimiento = models.DateField(blank=True, null=True)
    
    observaciones = models.TextField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'facturas'
        verbose_name_plural = 'Facturas'
        ordering = ['-fecha_emision']
    
    def __str__(self):
        cliente_info = f"{self.cliente.nombre} {self.cliente.apellidos}" if self.cliente else "Sin cliente"
        return f"Factura #{self.numero} - {cliente_info}"

# ============================================
# ÓRDENES
# ============================================

class Orden(models.Model):
    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('completada', 'Completada'),
        ('cancelada', 'Cancelada'),
    ]
    
    cliente = models.ForeignKey(Cliente, on_delete=models.SET_NULL, null=True, related_name='ordenes')
    factura = models.OneToOneField(Factura, on_delete=models.SET_NULL, null=True, blank=True, related_name='orden')
    
    metodo_pago = models.CharField(max_length=100)
    subtotal = models.DecimalField(decimal_places=2, max_digits=15, default=0)
    impuesto = models.DecimalField(decimal_places=2, max_digits=15, default=0)
    precio_total = models.DecimalField(decimal_places=2, max_digits=15)
    
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='pendiente')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'ordenes'
        ordering = ['-created_at']
    
    def __str__(self):
        cliente_info = f"{self.cliente.nombre} {self.cliente.apellidos}" if self.cliente else "Sin cliente"
        return f"Orden #{self.id} - {cliente_info}"

class OrdenItem(models.Model):
    orden = models.ForeignKey(Orden, on_delete=models.CASCADE, related_name='items')  # ← Relación FK
    detalle = models.CharField(max_length=150)
    precio = models.DecimalField(decimal_places=2, max_digits=15)  # ← Cambié de SmallIntegerField
    cantidad = models.PositiveIntegerField()  # ← PositiveIntegerField es mejor
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'orden_items'

    @property
    def subtotal(self):
        return self.precio * self.cantidad
    
    def __str__(self):
        return f"{self.detalle} - Orden #{self.orden.id}"

# ============================================
# COMPRAS
# ============================================

class Proveedor(models.Model):
    nombre = models.CharField(max_length=150)
    documento = models.CharField(max_length=50, blank=True, null=True, help_text="NIT, cédula o identificación")
    telefono = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    direccion = models.CharField(max_length=255, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'proveedores'
        ordering = ['nombre']

    def __str__(self):
        return self.nombre

class Compra(models.Model):
    ESTADO_CHOICES = [
        ('borrador', 'Borrador'),
        ('en_espera', 'En espera'),
        ('completada', 'Completada'),
        ('anulada', 'Anulada'),
    ]
    METODO_PAGO_CHOICES = [
        ('efectivo', 'Efectivo'),
        ('tarjeta', 'Tarjeta'),
        ('transferencia', 'Transferencia'),
        ('credito', 'Crédito'),
        ('otro', 'Otro'),
    ]

    proveedor = models.ForeignKey(Proveedor, on_delete=models.SET_NULL, null=True, blank=True, related_name='compras')
    numero_factura = models.CharField(max_length=50, blank=True, null=True)
    fecha_compra = models.DateField()
    subtotal = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    impuesto = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    metodo_pago = models.CharField(max_length=100, choices=METODO_PAGO_CHOICES, blank=True, null=True)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='borrador')
    stock_aplicado = models.BooleanField(default=False)
    observaciones = models.TextField(blank=True, null=True)
    motivo_anulacion = models.TextField(blank=True, null=True)
    anulada_en = models.DateTimeField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'compras'
        ordering = ['-fecha_compra', '-created_at']

    def __str__(self):
        proveedor = self.proveedor.nombre if self.proveedor else "Sin proveedor"
        return f"Compra #{self.id} - {proveedor}"

    def aplicar_stock(self):
        if self.stock_aplicado:
            return

        for item in self.items.select_related('producto'):
            item.producto.stock += item.cantidad
            item.producto.save()

        self.stock_aplicado = True
        self.save(update_fields=['stock_aplicado', 'updated_at'])

    def anular(self, motivo=''):
        self.estado = 'anulada'
        self.motivo_anulacion = motivo
        self.anulada_en = timezone.now()
        self.save(update_fields=['estado', 'motivo_anulacion', 'anulada_en', 'updated_at'])

class CompraItem(models.Model):
    compra = models.ForeignKey(Compra, on_delete=models.CASCADE, related_name='items')
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT, related_name='compras_items')
    cantidad = models.PositiveIntegerField()
    costo_unitario = models.DecimalField(max_digits=15, decimal_places=2)
    subtotal = models.DecimalField(max_digits=15, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'compra_items'

    def __str__(self):
        return f"{self.producto.nombre} x {self.cantidad}"
