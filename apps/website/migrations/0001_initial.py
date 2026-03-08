from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('crm', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ContactMessage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200, verbose_name='Nombre')),
                ('email', models.EmailField(max_length=254, verbose_name='Correo Electrónico')),
                ('phone', models.CharField(blank=True, max_length=20, verbose_name='Teléfono')),
                ('company', models.CharField(blank=True, max_length=200, verbose_name='Empresa')),
                ('ruc', models.CharField(blank=True, max_length=11, verbose_name='RUC')),
                ('service_interest', models.CharField(
                    choices=[
                        ('facturacion', 'Facturación Electrónica'),
                        ('rpa', 'Automatización de Procesos (RPA)'),
                        ('marketing', 'Marketing Pos-venta'),
                        ('web', 'Desarrollo Web'),
                        ('consultoria', 'Consultoría Informática'),
                        ('erp', 'Sistema ERP / POS'),
                        ('other', 'Otro'),
                    ],
                    default='consultoria', max_length=20, verbose_name='Servicio de Interés',
                )),
                ('message', models.TextField(verbose_name='Mensaje')),
                ('status', models.CharField(
                    choices=[
                        ('new', 'Nuevo'),
                        ('read', 'Leído'),
                        ('converted', 'Convertido a Oportunidad'),
                        ('archived', 'Archivado'),
                    ],
                    default='new', max_length=20,
                )),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('opportunity', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='contact_messages', to='crm.opportunity',
                    verbose_name='Oportunidad Asociada',
                )),
            ],
            options={
                'verbose_name': 'Mensaje de Contacto',
                'verbose_name_plural': 'Mensajes de Contacto',
                'ordering': ['-created_at'],
            },
        ),
    ]
