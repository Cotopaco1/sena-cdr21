from django import forms
from django.contrib.auth.models import Group, User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from cdr22.models import ConfiguracionSistema
from cdr22.roles import ROLE_NAMES


class UsuarioCreateForm(forms.Form):
    PASSWORD_MODE_CHOICES = [
        ('manual', 'Definir contraseña ahora'),
        ('email', 'Enviar correo para configurar contraseña'),
    ]

    first_name = forms.CharField(label='Nombre', max_length=150)
    last_name = forms.CharField(label='Apellido', max_length=150, required=False)
    username = forms.CharField(label='Usuario', max_length=150)
    email = forms.EmailField(label='Correo electrónico')
    role = forms.ModelChoiceField(label='Rol', queryset=Group.objects.none())
    password_mode = forms.ChoiceField(label='Modo de contraseña', choices=PASSWORD_MODE_CHOICES)
    password1 = forms.CharField(label='Contraseña', required=False, widget=forms.PasswordInput)
    password2 = forms.CharField(label='Confirmar contraseña', required=False, widget=forms.PasswordInput)
    is_active = forms.BooleanField(label='Usuario activo', required=False, initial=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['role'].queryset = Group.objects.filter(name__in=ROLE_NAMES).order_by('name')

    def clean_username(self):
        username = self.cleaned_data['username'].strip()
        if User.objects.filter(username__iexact=username).exists():
            raise ValidationError('Ya existe un usuario con este nombre de usuario.')
        return username

    def clean_email(self):
        email = self.cleaned_data['email'].strip()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError('Ya existe un usuario con este correo electrónico.')
        return email

    def clean(self):
        cleaned_data = super().clean()
        password_mode = cleaned_data.get('password_mode')
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')

        if password_mode == 'manual':
            if not password1:
                self.add_error('password1', 'Ingrese una contraseña.')
            if not password2:
                self.add_error('password2', 'Confirme la contraseña.')
            if password1 and password2 and password1 != password2:
                self.add_error('password2', 'Las contraseñas no coinciden.')
            if password1:
                user = User(
                    username=cleaned_data.get('username', ''),
                    email=cleaned_data.get('email', ''),
                    first_name=cleaned_data.get('first_name', ''),
                    last_name=cleaned_data.get('last_name', ''),
                )
                try:
                    validate_password(password1, user=user)
                except ValidationError as error:
                    self.add_error('password1', error)
        elif password_mode == 'email' and not cleaned_data.get('is_active'):
            self.add_error('is_active', 'El usuario debe estar activo para enviar el correo de configuración de contraseña.')

        return cleaned_data


class PerfilUsuarioForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']
        labels = {
            'first_name': 'Nombre',
            'last_name': 'Apellido',
            'email': 'Correo electrónico',
        }

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip()
        if email and User.objects.exclude(pk=self.instance.pk).filter(email__iexact=email).exists():
            raise ValidationError('Ya existe otro usuario con este correo electrónico.')
        return email


class ConfiguracionSistemaForm(forms.ModelForm):
    class Meta:
        model = ConfiguracionSistema
        fields = [
            'nombre_empresa',
            'nit_empresa',
            'direccion_empresa',
            'ciudad_empresa',
            'pais_empresa',
            'telefono_empresa',
            'email_empresa',
            'logo',
            'prefijo_factura',
            'siguiente_numero_factura',
            'impuesto_porcentaje',
            'moneda',
        ]

    def clean_nit_empresa(self):
        nit = self.cleaned_data.get('nit_empresa') or ''
        return nit.strip()

    def clean_logo(self):
        logo = self.cleaned_data.get('logo')
        if not logo:
            return logo

        if logo.size > 2 * 1024 * 1024:
            raise ValidationError('El logo no debe superar 2 MB.')

        return logo

    def clean_prefijo_factura(self):
        prefijo = self.cleaned_data['prefijo_factura'].strip().upper()
        if not prefijo:
            raise ValidationError('Ingrese un prefijo de factura.')
        return prefijo

    def clean_siguiente_numero_factura(self):
        siguiente_numero = self.cleaned_data['siguiente_numero_factura']
        if siguiente_numero < 1:
            raise ValidationError('El siguiente número debe ser mayor o igual a 1.')
        return siguiente_numero

    def clean_impuesto_porcentaje(self):
        impuesto = self.cleaned_data['impuesto_porcentaje']
        if impuesto < 0:
            raise ValidationError('El impuesto no puede ser negativo.')
        return impuesto


class ConfiguracionWhatsAppForm(forms.ModelForm):
    class Meta:
        model = ConfiguracionSistema
        fields = [
            'whatsapp_habilitado',
            'whatsapp_template_factura',
            'whatsapp_template_language',
            'whatsapp_numero_prueba',
        ]
        labels = {
            'whatsapp_habilitado': 'Habilitar envío por WhatsApp',
            'whatsapp_template_factura': 'Nombre de plantilla de factura',
            'whatsapp_template_language': 'Idioma de plantilla',
            'whatsapp_numero_prueba': 'Número de prueba',
        }

    def clean_whatsapp_template_factura(self):
        template = self.cleaned_data.get('whatsapp_template_factura') or ''
        return template.strip()

    def clean_whatsapp_template_language(self):
        language = self.cleaned_data.get('whatsapp_template_language') or ''
        language = language.strip()
        if not language:
            raise ValidationError('Ingrese el idioma de la plantilla.')
        return language

    def clean_whatsapp_numero_prueba(self):
        numero = self.cleaned_data.get('whatsapp_numero_prueba') or ''
        return numero.replace('+', '').replace(' ', '').replace('-', '').strip()

    def clean(self):
        cleaned_data = super().clean()
        habilitado = cleaned_data.get('whatsapp_habilitado')
        template = cleaned_data.get('whatsapp_template_factura')

        if habilitado and not template:
            self.add_error('whatsapp_template_factura', 'Ingrese la plantilla para habilitar WhatsApp.')

        return cleaned_data
