"""
Seed realistic test data for the Peruvian ERP system.
Creates customers, suppliers, products with stock, and sample sales.
"""
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
import random

from apps.core.models import Company, Branch, Currency, User
from apps.crm.models import Customer, Supplier, Opportunity, Interaction
from apps.logistics.models import (
    Product, Category, Brand, UnitOfMeasure, Warehouse, StockLevel, StockMovement
)
from apps.accounting.models import DocumentSeries, Invoice, InvoiceItem, AccountReceivable
from apps.pos.models import CashRegister, CashSession, POSSale, POSSaleItem


class Command(BaseCommand):
    help = 'Seed realistic Peruvian test data (customers, products, stock, sales)'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('Cargando data de prueba peruana...'))

        # Ensure base data exists
        branch = Branch.objects.filter(is_main=True).first()
        if not branch:
            self.stdout.write(self.style.ERROR('Ejecute primero: python manage.py seed_initial_data'))
            return

        warehouse = Warehouse.objects.filter(is_default=True).first()
        default_unit = UnitOfMeasure.objects.filter(code='NIU').first()
        kg_unit = UnitOfMeasure.objects.filter(code='KGM').first()
        lt_unit = UnitOfMeasure.objects.filter(code='LTR').first()
        srv_unit = UnitOfMeasure.objects.filter(code='ZZ').first()

        # ===== BRANDS =====
        brands_data = [
            'Samsung', 'Apple', 'Lenovo', 'HP', 'Gloria', 'Laive',
            'Alicorp', 'Backus', 'Coca-Cola', 'Adidas', 'Nike',
            'Epson', 'Canon', 'LG', 'Xiaomi', 'Huawei',
        ]
        brands = {}
        for name in brands_data:
            brand, _ = Brand.objects.get_or_create(
                slug=name.lower().replace(' ', '-'),
                defaults={'name': name}
            )
            brands[name] = brand

        # ===== CATEGORIES (ensure they exist) =====
        cat_map = {}
        for cat in Category.objects.all():
            cat_map[cat.name] = cat

        # ===== PRODUCTS =====
        products_data = [
            # Electronica
            ('PROD-001', 'Laptop Lenovo IdeaPad 15', 'Electronica', 'Lenovo', 2200, 3499, 3299, default_unit, '10'),
            ('PROD-002', 'Monitor Samsung 24" Full HD', 'Electronica', 'Samsung', 450, 799, 749, default_unit, '10'),
            ('PROD-003', 'Teclado Mecanico RGB', 'Electronica', None, 85, 159, 145, default_unit, '10'),
            ('PROD-004', 'Mouse Inalambrico Logitech', 'Electronica', None, 35, 69, 59, default_unit, '10'),
            ('PROD-005', 'Audifono Bluetooth JBL', 'Electronica', None, 120, 249, 229, default_unit, '10'),
            ('PROD-006', 'Impresora Epson L3250', 'Electronica', 'Epson', 580, 899, 849, default_unit, '10'),
            ('PROD-007', 'Celular Xiaomi Redmi Note 13', 'Electronica', 'Xiaomi', 550, 999, 949, default_unit, '10'),
            ('PROD-008', 'Tablet Samsung Galaxy A9', 'Electronica', 'Samsung', 700, 1299, 1199, default_unit, '10'),
            ('PROD-009', 'Cable HDMI 2m', 'Electronica', None, 8, 25, 20, default_unit, '10'),
            ('PROD-010', 'Cargador USB-C Rapido', 'Electronica', None, 15, 45, 39, default_unit, '10'),

            # Alimentos y Bebidas
            ('PROD-011', 'Arroz Extra Costeño 5kg', 'Alimentos y Bebidas', None, 14, 22.90, 21, kg_unit, '10'),
            ('PROD-012', 'Aceite Vegetal Primor 1L', 'Alimentos y Bebidas', None, 6, 11.50, 10.50, lt_unit, '10'),
            ('PROD-013', 'Leche Gloria Entera 1L', 'Alimentos y Bebidas', 'Gloria', 3.20, 5.90, 5.50, lt_unit, '10'),
            ('PROD-014', 'Azucar Rubia 1kg', 'Alimentos y Bebidas', None, 2.80, 4.90, 4.50, kg_unit, '10'),
            ('PROD-015', 'Fideos Don Vittorio 500g', 'Alimentos y Bebidas', None, 2.50, 4.50, 4, default_unit, '10'),
            ('PROD-016', 'Agua San Luis 2.5L', 'Alimentos y Bebidas', None, 1.50, 3.50, 3, lt_unit, '10'),
            ('PROD-017', 'Gaseosa Inca Kola 1.5L', 'Alimentos y Bebidas', 'Coca-Cola', 3.50, 6.90, 6.50, lt_unit, '10'),
            ('PROD-018', 'Cerveza Cristal Pack x6', 'Alimentos y Bebidas', 'Backus', 18, 29.90, 27.90, default_unit, '10'),
            ('PROD-019', 'Cafe Altomayo 200g', 'Alimentos y Bebidas', None, 12, 22.90, 20.90, default_unit, '10'),
            ('PROD-020', 'Galletas Soda Field 6 pack', 'Alimentos y Bebidas', None, 3, 5.90, 5.50, default_unit, '10'),

            # Oficina
            ('PROD-021', 'Papel Bond A4 x500 hojas', 'Oficina', None, 12, 22.90, 20.90, default_unit, '10'),
            ('PROD-022', 'Lapiceros Faber Castell x12', 'Oficina', None, 6, 14.90, 13.50, default_unit, '10'),
            ('PROD-023', 'Archivador Artesco A4', 'Oficina', None, 4, 9.90, 8.90, default_unit, '10'),
            ('PROD-024', 'Cinta de Embalaje Transparente', 'Oficina', None, 3, 7.90, 6.90, default_unit, '10'),
            ('PROD-025', 'Toner HP 107A Original', 'Oficina', 'HP', 120, 199, 185, default_unit, '10'),

            # Ropa y Accesorios
            ('PROD-026', 'Polo Algodon Pima Hombre', 'Ropa y Accesorios', None, 18, 39.90, 35, default_unit, '10'),
            ('PROD-027', 'Jean Clasico Hombre', 'Ropa y Accesorios', None, 35, 79.90, 69.90, default_unit, '10'),
            ('PROD-028', 'Zapatillas Deportivas Nike', 'Ropa y Accesorios', 'Nike', 180, 349, 299, default_unit, '10'),
            ('PROD-029', 'Mochila Escolar 20L', 'Ropa y Accesorios', None, 25, 59.90, 49.90, default_unit, '10'),
            ('PROD-030', 'Gorra Bordada Peru', 'Ropa y Accesorios', None, 8, 19.90, 17.90, default_unit, '10'),

            # Hogar
            ('PROD-031', 'Detergente Ace 2.6kg', 'Hogar y Jardin', None, 14, 25.90, 23.90, default_unit, '10'),
            ('PROD-032', 'Lejia Clorox 1L', 'Hogar y Jardin', None, 3, 6.90, 5.90, lt_unit, '10'),
            ('PROD-033', 'Escoba con Recogedor', 'Hogar y Jardin', None, 8, 17.90, 15.90, default_unit, '10'),
            ('PROD-034', 'Foco LED 12W Philips', 'Hogar y Jardin', None, 5, 12.90, 10.90, default_unit, '10'),
            ('PROD-035', 'Extension Electrica 3m', 'Hogar y Jardin', None, 10, 22.90, 19.90, default_unit, '10'),

            # Salud y Belleza
            ('PROD-036', 'Jabon Dove Barra x3', 'Salud y Belleza', None, 8, 14.90, 12.90, default_unit, '10'),
            ('PROD-037', 'Shampoo Head & Shoulders 375ml', 'Salud y Belleza', None, 12, 22.90, 19.90, default_unit, '10'),
            ('PROD-038', 'Crema Dental Colgate 150ml', 'Salud y Belleza', None, 4, 8.90, 7.90, default_unit, '10'),
            ('PROD-039', 'Alcohol en Gel 500ml', 'Salud y Belleza', None, 6, 12.90, 10.90, default_unit, '10'),
            ('PROD-040', 'Mascarillas KN95 x10', 'Salud y Belleza', None, 8, 19.90, 16.90, default_unit, '10'),

            # Servicios
            ('SRV-001', 'Servicio de Instalacion', 'Servicios', None, 0, 80, 70, srv_unit, '10'),
            ('SRV-002', 'Soporte Tecnico por Hora', 'Servicios', None, 0, 50, 45, srv_unit, '10'),
            ('SRV-003', 'Configuracion de Red', 'Servicios', None, 0, 150, 130, srv_unit, '10'),
        ]

        created_products = []
        for sku, name, cat_name, brand_name, purchase, sale, wholesale, unit, affect in products_data:
            cat = cat_map.get(cat_name)
            brand = brands.get(brand_name) if brand_name else None
            prod, created = Product.objects.update_or_create(
                sku=sku,
                defaults={
                    'name': name,
                    'category': cat,
                    'brand': brand,
                    'unit': unit or default_unit,
                    'purchase_price': Decimal(str(purchase)),
                    'sale_price': Decimal(str(sale)),
                    'wholesale_price': Decimal(str(wholesale)),
                    'minimum_price': Decimal(str(purchase * 1.1)),
                    'affectation_type': affect,
                    'is_active': True,
                    'track_inventory': not sku.startswith('SRV'),
                    'min_stock': 5 if not sku.startswith('SRV') else 0,
                    'max_stock': 100 if not sku.startswith('SRV') else 0,
                    'product_type': 'service' if sku.startswith('SRV') else 'product',
                }
            )
            created_products.append(prod)
            action = 'Creado' if created else 'Actualizado'
            self.stdout.write(f'  {action}: Producto {sku} - {name}')

        # ===== STOCK LEVELS =====
        if warehouse:
            for prod in created_products:
                if prod.track_inventory:
                    qty = random.randint(10, 150)
                    stock, created = StockLevel.objects.update_or_create(
                        product=prod, warehouse=warehouse,
                        defaults={'quantity': qty}
                    )
                    if created:
                        StockMovement.objects.create(
                            movement_type='in',
                            product=prod,
                            warehouse=warehouse,
                            quantity=qty,
                            unit_cost=prod.purchase_price,
                            reference='CARGA-INICIAL',
                            reference_type='initial_load',
                            reason='Carga inicial de inventario',
                        )

        # ===== CUSTOMERS =====
        customers_data = [
            ('RUC', '20100130204', 'SUPERMERCADOS PERUANOS S.A.', 'business', 'contacto@spsa.pe', '014116000', 'Calle Morelli 181, San Borja, Lima', '150141', 'Lima', 'Lima', 'San Borja', 50000, 60),
            ('RUC', '20100070970', 'TIENDAS POR DEPARTAMENTO RIPLEY S.A.', 'business', 'proveedores@ripley.com.pe', '016130700', 'Av. Las Begonias 545, San Isidro, Lima', '150131', 'Lima', 'Lima', 'San Isidro', 80000, 45),
            ('RUC', '20305087781', 'FERRETERIA INDUSTRIAL SAC', 'business', 'compras@ferreteriaindustrial.pe', '014565890', 'Jr. Union 456, Cercado de Lima', '150101', 'Lima', 'Lima', 'Cercado de Lima', 30000, 30),
            ('RUC', '20512345678', 'RESTAURANTE EL BUEN SABOR EIRL', 'business', 'admin@elbuensabor.pe', '016789012', 'Av. Larco 345, Miraflores, Lima', '150122', 'Lima', 'Lima', 'Miraflores', 15000, 30),
            ('RUC', '20601234567', 'CONSULTORA TECH SOLUTIONS SAC', 'business', 'info@techsolutions.pe', '017891234', 'Av. Javier Prado 1234, San Isidro', '150131', 'Lima', 'Lima', 'San Isidro', 25000, 45),
            ('DNI', '45678912', 'GARCIA LOPEZ MARIA ELENA', 'individual', 'maria.garcia@gmail.com', '987654321', 'Av. Brasil 1234, Jesus Maria, Lima', '150111', 'Lima', 'Lima', 'Jesus Maria', 5000, 15),
            ('DNI', '78901234', 'RODRIGUEZ QUISPE JUAN CARLOS', 'individual', 'jrodriguez@hotmail.com', '976543210', 'Jr. Huallaga 890, Cercado de Lima', '150101', 'Lima', 'Lima', 'Cercado de Lima', 3000, 0),
            ('DNI', '32165498', 'FERNANDEZ TORRES ANA LUCIA', 'individual', 'afernandez@outlook.com', '965432109', 'Calle Las Flores 567, San Miguel', '150136', 'Lima', 'Lima', 'San Miguel', 2000, 0),
            ('DNI', '12345678', 'MARTINEZ HUAMAN PEDRO', 'individual', 'pmartinez@gmail.com', '954321098', 'Av. Colonial 2345, Callao', '070101', 'Callao', 'Callao', 'Callao', 1000, 0),
            ('DNI', '87654321', 'DIAZ PAREDES ROSA ISABEL', 'individual', 'rdiaz@gmail.com', '943210987', 'Jr. Cusco 678, La Victoria, Lima', '150115', 'Lima', 'Lima', 'La Victoria', 2000, 15),
            ('DNI', '00000000', 'CLIENTES VARIOS', 'individual', '', '', '', '', '', '', '', 0, 0),
        ]

        admin_user = User.objects.filter(is_superuser=True).first()
        created_customers = []
        for doc_type, doc_num, name, ctype, email, phone, address, ubigeo, dept, prov, dist, credit, days in customers_data:
            cust, created = Customer.objects.update_or_create(
                doc_number=doc_num,
                defaults={
                    'doc_type': doc_type,
                    'name': name,
                    'customer_type': ctype,
                    'email': email,
                    'phone': phone,
                    'address': address,
                    'ubigeo': ubigeo,
                    'department': dept,
                    'province': prov,
                    'district': dist,
                    'credit_limit': Decimal(str(credit)),
                    'credit_days': days,
                    'is_active': True,
                    'created_by': admin_user,
                }
            )
            created_customers.append(cust)
            action = 'Creado' if created else 'Actualizado'
            self.stdout.write(f'  {action}: Cliente {doc_num} - {name}')

        # ===== SUPPLIERS =====
        suppliers_data = [
            ('RUC', '20100055237', 'IMPORTADORA Y DISTRIBUIDORA SAC', 'contacto@importadora.pe', '014567890', 'Av. Argentina 2345, Lima', 'Juan Perez', 30, 'BCP', '191-123456789-0-12', '002-191-123456789012-01'),
            ('RUC', '20382036655', 'DISTRIBUIDORA ALICORP SAC', 'ventas@alicorp.pe', '013155000', 'Av. Argentina 4793, Callao', 'Carlos Ruiz', 45, 'BBVA', '011-987654321-0-01', '011-987654321012345-01'),
            ('RUC', '20100028698', 'GLORIA S.A.', 'proveedores@gloria.com.pe', '014700200', 'Av. Republica de Panama 2461, La Victoria', 'Ana Torres', 30, 'Scotiabank', '009-111222333-0-01', '009-111222333012345-01'),
            ('RUC', '20513267851', 'TECH IMPORTACIONES PERU EIRL', 'compras@techimport.pe', '017654321', 'Jr. Lampa 345, Cercado de Lima', 'Roberto Silva', 60, 'Interbank', '200-444555666-0-01', '003-200-444555666012-01'),
            ('RUC', '20498765432', 'PAPELERA DEL SUR SAC', 'ventas@papeleradelsur.pe', '016543210', 'Av. Los Frutales 678, Ate', 'Lucia Mendoza', 30, 'BCP', '191-777888999-0-12', '002-191-777888999012-01'),
        ]

        for doc_type, doc_num, name, email, phone, address, contact, terms, bank, account, cci in suppliers_data:
            sup, created = Supplier.objects.update_or_create(
                doc_number=doc_num,
                defaults={
                    'doc_type': doc_type,
                    'name': name,
                    'email': email,
                    'phone': phone,
                    'address': address,
                    'contact_name': contact,
                    'payment_terms': terms,
                    'bank_name': bank,
                    'bank_account': account,
                    'bank_cci': cci,
                    'is_active': True,
                }
            )
            action = 'Creado' if created else 'Actualizado'
            self.stdout.write(f'  {action}: Proveedor {doc_num} - {name}')

        # ===== CRM OPPORTUNITIES =====
        if admin_user and len(created_customers) >= 5:
            opportunities_data = [
                (created_customers[0], 'Licitacion equipos de computo 2026', 'Renovacion de 50 laptops', 'proposal', 'high', 175000, 70),
                (created_customers[1], 'Contrato de suministro mensual', 'Productos de oficina recurrentes', 'negotiation', 'urgent', 48000, 85),
                (created_customers[2], 'Proyecto de redes y cableado', 'Instalacion de red en nueva sede', 'qualification', 'medium', 35000, 45),
                (created_customers[4], 'Migracion a cloud', 'Consultoria y migracion de servidores', 'prospecting', 'medium', 25000, 30),
            ]
            for cust, title, desc, stage, priority, amount, prob in opportunities_data:
                opp, created = Opportunity.objects.update_or_create(
                    title=title,
                    defaults={
                        'customer': cust,
                        'description': desc,
                        'stage': stage,
                        'priority': priority,
                        'expected_amount': Decimal(str(amount)),
                        'probability': prob,
                        'expected_close_date': timezone.now().date() + timedelta(days=random.randint(15, 90)),
                        'assigned_to': admin_user,
                        'source': 'Referencia directa',
                    }
                )

        self.stdout.write(self.style.SUCCESS(
            f'\nData de prueba cargada exitosamente:\n'
            f'  - {len(products_data)} productos\n'
            f'  - {len(customers_data)} clientes\n'
            f'  - {len(suppliers_data)} proveedores\n'
            f'  - {len(brands_data)} marcas\n'
            f'  - Stock inicial configurado\n'
            f'  - Oportunidades CRM creadas'
        ))
