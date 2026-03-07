"""
Management command to seed initial data for the ERP system.
Creates company, branch, warehouse, currencies, units of measure,
document series, cash register, and sample categories.
"""
from django.core.management.base import BaseCommand
from django.conf import settings

from apps.core.models import Company, Branch, Currency, SystemConfig
from apps.logistics.models import Category, UnitOfMeasure, Warehouse
from apps.accounting.models import DocumentSeries
from apps.pos.models import CashRegister


class Command(BaseCommand):
    help = 'Seed initial data for the ERP system (company, branch, currencies, units, series)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset', action='store_true',
            help='Delete existing data before seeding',
        )

    def handle(self, *args, **options):
        if options['reset']:
            self.stdout.write(self.style.WARNING('Resetting seed data...'))

        # Company
        company_config = settings.COMPANY_CONFIG
        company, created = Company.objects.update_or_create(
            ruc=company_config['RUC'],
            defaults={
                'name': company_config['NAME'],
                'address': company_config['ADDRESS'],
                'phone': company_config.get('PHONE', ''),
                'email': company_config.get('EMAIL', ''),
                'website': company_config.get('WEBSITE', ''),
                'igv_rate': company_config.get('IGV_RATE', 0.18),
            }
        )
        self._log('Empresa', company.name, created)

        # Main Branch
        branch, created = Branch.objects.update_or_create(
            code='MAIN',
            defaults={
                'company': company,
                'name': 'Sede Principal',
                'address': company.address,
                'phone': company.phone,
                'is_main': True,
            }
        )
        self._log('Sucursal', branch.name, created)

        # Currencies
        currencies = [
            ('PEN', 'Sol Peruano', 'S/', 1, True),
            ('USD', 'Dólar Americano', '$', 3.75, False),
            ('EUR', 'Euro', '€', 4.10, False),
        ]
        for code, name, symbol, rate, is_default in currencies:
            obj, created = Currency.objects.update_or_create(
                code=code, defaults={'name': name, 'symbol': symbol, 'exchange_rate': rate, 'is_default': is_default}
            )
            self._log('Moneda', code, created)

        # SUNAT Units of Measure
        units = [
            ('NIU', 'Unidad', 'UND'),
            ('KGM', 'Kilogramo', 'KG'),
            ('LTR', 'Litro', 'LT'),
            ('MTR', 'Metro', 'MT'),
            ('MTK', 'Metro Cuadrado', 'M2'),
            ('MTQ', 'Metro Cúbico', 'M3'),
            ('GRM', 'Gramo', 'GR'),
            ('TNE', 'Tonelada', 'TN'),
            ('HUR', 'Hora', 'HR'),
            ('DAY', 'Día', 'DIA'),
            ('MON', 'Mes', 'MES'),
            ('ZZ', 'Servicio', 'SRV'),
            ('BX', 'Caja', 'CJ'),
            ('DZN', 'Docena', 'DOC'),
            ('PK', 'Paquete', 'PQT'),
            ('SET', 'Juego', 'JGO'),
            ('PR', 'Par', 'PAR'),
            ('GLL', 'Galón', 'GAL'),
            ('MLT', 'Mililitro', 'ML'),
            ('CMT', 'Centímetro', 'CM'),
        ]
        for code, name, abbreviation in units:
            obj, created = UnitOfMeasure.objects.update_or_create(
                code=code, defaults={'name': name, 'abbreviation': abbreviation}
            )
            self._log('Unidad', code, created)

        # Default Warehouse
        warehouse, created = Warehouse.objects.update_or_create(
            code='ALM-001',
            defaults={
                'name': 'Almacén Principal',
                'branch': branch,
                'is_default': True,
                'address': company.address,
            }
        )
        self._log('Almacén', warehouse.name, created)

        # Document Series (SUNAT)
        series_data = [
            ('01', 'F001', 'Factura'),
            ('03', 'B001', 'Boleta'),
            ('07', 'FC01', 'Nota de Crédito'),
            ('08', 'FD01', 'Nota de Débito'),
        ]
        for doc_type, series, desc in series_data:
            obj, created = DocumentSeries.objects.update_or_create(
                doc_type=doc_type, series=series,
                defaults={'branch': branch, 'next_correlative': 1, 'is_active': True}
            )
            self._log(f'Serie {desc}', series, created)

        # Cash Register
        register, created = CashRegister.objects.update_or_create(
            code='CAJA-001',
            defaults={'name': 'Caja Principal', 'branch': branch, 'is_active': True}
        )
        self._log('Caja', register.name, created)

        # Product Categories
        categories = [
            ('Electrónica', 'electronica'),
            ('Ropa y Accesorios', 'ropa-accesorios'),
            ('Alimentos y Bebidas', 'alimentos-bebidas'),
            ('Hogar y Jardín', 'hogar-jardin'),
            ('Oficina', 'oficina'),
            ('Salud y Belleza', 'salud-belleza'),
            ('Deportes', 'deportes'),
            ('Servicios', 'servicios'),
        ]
        for i, (name, slug) in enumerate(categories):
            obj, created = Category.objects.update_or_create(
                slug=slug, defaults={'name': name, 'order': i}
            )
            self._log('Categoría', name, created)

        # System Config
        configs = [
            ('igv_rate', '0.18', 'Tasa de IGV'),
            ('default_currency', 'PEN', 'Moneda por defecto'),
            ('receipt_footer', 'Gracias por su compra', 'Pie de recibo'),
            ('low_stock_threshold', '10', 'Umbral de stock bajo'),
        ]
        for key, value, desc in configs:
            obj, created = SystemConfig.objects.update_or_create(
                key=key, defaults={'value': value, 'description': desc}
            )
            self._log('Config', key, created)

        self.stdout.write(self.style.SUCCESS('\nDatos iniciales cargados exitosamente.'))

    def _log(self, entity, name, created):
        action = 'Creado' if created else 'Actualizado'
        style = self.style.SUCCESS if created else self.style.WARNING
        self.stdout.write(style(f'  {action}: {entity} - {name}'))
