"""
SUNAT Integration Services.
Handles electronic invoicing (facturacion electronica) with SUNAT Peru.
All features gated by FeatureFlag model for testing/production control.
"""
import base64
import hashlib
import io
import logging
import os
import zipfile
from decimal import Decimal, ROUND_HALF_UP
from xml.etree import ElementTree as ET

import requests
from django.conf import settings
from django.core.files.base import ContentFile

from .models import SunatLog

logger = logging.getLogger(__name__)

# SUNAT Document type codes
SUNAT_DOC_TYPES = {
    '01': 'Factura',
    '03': 'Boleta de Venta',
    '07': 'Nota de Crédito',
    '08': 'Nota de Débito',
}

# SUNAT Identity document type codes
SUNAT_IDENTITY_TYPES = {
    'DNI': '1',
    'RUC': '6',
    'CE': '4',
    'PAS': '7',
}

# IGV Affectation types
IGV_AFFECTATION = {
    '10': {'name': 'Gravado', 'code': '1000', 'rate': Decimal('0.18'), 'category': 'S'},
    '20': {'name': 'Exonerado', 'code': '9997', 'rate': Decimal('0'), 'category': 'E'},
    '30': {'name': 'Inafecto', 'code': '9998', 'rate': Decimal('0'), 'category': 'O'},
    '21': {'name': 'Gratuito', 'code': '9996', 'rate': Decimal('0'), 'category': 'Z'},
}

# Nota de Credito - Tipos de motivo (Catalogo 09)
NC_REASON_TYPES = {
    '01': 'Anulacion de la operacion',
    '02': 'Anulacion por error en el RUC',
    '03': 'Correccion por error en la descripcion',
    '04': 'Descuento global',
    '05': 'Descuento por item',
    '06': 'Devolucion total',
    '07': 'Devolucion por item',
    '08': 'Bonificacion',
    '09': 'Disminucion en el valor',
    '10': 'Otros conceptos',
}

# Nota de Debito - Tipos de motivo (Catalogo 10)
ND_REASON_TYPES = {
    '01': 'Intereses por mora',
    '02': 'Aumento en el valor',
    '03': 'Penalidades/ otros conceptos',
}


def _flag_active(code):
    """Check if a feature flag is active."""
    from apps.core.models import FeatureFlag
    return FeatureFlag.is_active(code)


def amount_to_words(amount):
    """Convert numeric amount to Spanish words for Peru invoicing."""
    if not _flag_active('invoice_amount_in_words'):
        return ''

    units = ['', 'UN', 'DOS', 'TRES', 'CUATRO', 'CINCO', 'SEIS', 'SIETE', 'OCHO', 'NUEVE']
    teens = ['DIEZ', 'ONCE', 'DOCE', 'TRECE', 'CATORCE', 'QUINCE',
             'DIECISEIS', 'DIECISIETE', 'DIECIOCHO', 'DIECINUEVE']
    tens = ['', '', 'VEINTE', 'TREINTA', 'CUARENTA', 'CINCUENTA',
            'SESENTA', 'SETENTA', 'OCHENTA', 'NOVENTA']
    hundreds = ['', 'CIENTO', 'DOSCIENTOS', 'TRESCIENTOS', 'CUATROCIENTOS', 'QUINIENTOS',
                'SEISCIENTOS', 'SETECIENTOS', 'OCHOCIENTOS', 'NOVECIENTOS']

    def _convert_group(n):
        if n == 0:
            return ''
        if n == 100:
            return 'CIEN'
        result = ''
        if n >= 100:
            result += hundreds[n // 100] + ' '
            n %= 100
        if n >= 20:
            result += tens[n // 10]
            remainder = n % 10
            if remainder:
                result += ' Y ' + units[remainder]
            return result.strip()
        if n >= 10:
            return result + teens[n - 10]
        if n > 0:
            return result + units[n]
        return result.strip()

    amount = Decimal(str(amount)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    integer_part = int(amount)
    decimal_part = int((amount - integer_part) * 100)

    if integer_part == 0:
        words = 'CERO'
    else:
        parts = []
        if integer_part >= 1000000:
            millions = integer_part // 1000000
            integer_part %= 1000000
            if millions == 1:
                parts.append('UN MILLON')
            else:
                parts.append(_convert_group(millions) + ' MILLONES')
        if integer_part >= 1000:
            thousands = integer_part // 1000
            integer_part %= 1000
            if thousands == 1:
                parts.append('MIL')
            else:
                parts.append(_convert_group(thousands) + ' MIL')
        if integer_part > 0:
            parts.append(_convert_group(integer_part))
        words = ' '.join(parts)

    return f"SON: {words} CON {decimal_part:02d}/100 SOLES"


class SunatService:
    """Service class for SUNAT electronic invoicing operations."""

    def __init__(self):
        config = settings.SUNAT_CONFIG
        self.ruc = config['RUC']
        self.user = config['USER']
        self.password = config['PASSWORD']
        self.production = config['PRODUCTION']
        self.base_url = config['PRODUCTION_URL'] if self.production else config['BETA_URL']

    # ========================================================================
    # XML BUILDING
    # ========================================================================

    def _ns(self):
        """XML namespaces for UBL 2.1."""
        return {
            'xmlns': 'urn:oasis:names:specification:ubl:schema:xsd:Invoice-2',
            'xmlns:cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2',
            'xmlns:cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
            'xmlns:ext': 'urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2',
            'xmlns:ds': 'http://www.w3.org/2000/09/xmldsig#',
        }

    def _add_supplier(self, root, company):
        """Add supplier (emisor) party to XML."""
        supplier_party = ET.SubElement(root, 'cac:AccountingSupplierParty')
        party = ET.SubElement(supplier_party, 'cac:Party')

        party_id = ET.SubElement(party, 'cac:PartyIdentification')
        pid = ET.SubElement(party_id, 'cbc:ID')
        pid.set('schemeID', '6')
        pid.text = company.ruc

        party_name = ET.SubElement(party, 'cac:PartyName')
        pname = ET.SubElement(party_name, 'cbc:Name')
        pname.text = company.trade_name or company.name

        party_legal = ET.SubElement(party, 'cac:PartyLegalEntity')
        reg_name = ET.SubElement(party_legal, 'cbc:RegistrationName')
        reg_name.text = company.name

        address = ET.SubElement(party_legal, 'cac:RegistrationAddress')
        addr_id = ET.SubElement(address, 'cbc:ID')
        addr_id.text = company.ubigeo or '150101'
        addr_type = ET.SubElement(address, 'cbc:AddressTypeCode')
        addr_type.text = '0000'

    def _add_customer(self, root, customer):
        """Add customer (adquiriente) party to XML."""
        customer_party = ET.SubElement(root, 'cac:AccountingCustomerParty')
        cparty = ET.SubElement(customer_party, 'cac:Party')

        cparty_id = ET.SubElement(cparty, 'cac:PartyIdentification')
        cpid = ET.SubElement(cparty_id, 'cbc:ID')
        cpid.set('schemeID', SUNAT_IDENTITY_TYPES.get(customer.doc_type, '1'))
        cpid.text = customer.doc_number

        cparty_legal = ET.SubElement(cparty, 'cac:PartyLegalEntity')
        creg_name = ET.SubElement(cparty_legal, 'cbc:RegistrationName')
        creg_name.text = customer.name

    def _add_tax_totals(self, root, invoice):
        """Add properly split tax totals by affectation type."""
        currency = invoice.currency.code if invoice.currency else 'PEN'

        # Main tax total
        tax_total = ET.SubElement(root, 'cac:TaxTotal')
        tax_amount = ET.SubElement(tax_total, 'cbc:TaxAmount')
        tax_amount.set('currencyID', currency)
        tax_amount.text = str(invoice.igv)

        # Subtotal for Gravado (IGV)
        if invoice.op_gravada > 0:
            self._add_tax_subtotal(tax_total, currency, invoice.op_gravada, invoice.igv, '1000', 'IGV', 'VAT', 'S')

        # Subtotal for Exonerado
        if invoice.op_exonerada > 0:
            self._add_tax_subtotal(tax_total, currency, invoice.op_exonerada, Decimal('0'), '9997', 'EXO', 'VAT', 'E')

        # Subtotal for Inafecto
        if invoice.op_inafecta > 0:
            self._add_tax_subtotal(tax_total, currency, invoice.op_inafecta, Decimal('0'), '9998', 'INA', 'FRE', 'O')

        # Subtotal for Gratuito
        if invoice.op_gratuita > 0:
            self._add_tax_subtotal(tax_total, currency, invoice.op_gratuita, Decimal('0'), '9996', 'GRA', 'FRE', 'Z')

    def _add_tax_subtotal(self, parent, currency, taxable, tax_amount_val, scheme_id, scheme_name, tax_type, category_id):
        sub = ET.SubElement(parent, 'cac:TaxSubtotal')
        taxable_elem = ET.SubElement(sub, 'cbc:TaxableAmount')
        taxable_elem.set('currencyID', currency)
        taxable_elem.text = str(taxable)

        tax_amt = ET.SubElement(sub, 'cbc:TaxAmount')
        tax_amt.set('currencyID', currency)
        tax_amt.text = str(tax_amount_val)

        cat = ET.SubElement(sub, 'cac:TaxCategory')
        cat_id = ET.SubElement(cat, 'cbc:ID')
        cat_id.text = category_id

        scheme = ET.SubElement(cat, 'cac:TaxScheme')
        s_id = ET.SubElement(scheme, 'cbc:ID')
        s_id.text = scheme_id
        s_name = ET.SubElement(scheme, 'cbc:Name')
        s_name.text = scheme_name
        s_code = ET.SubElement(scheme, 'cbc:TaxTypeCode')
        s_code.text = tax_type

    def _add_invoice_lines(self, root, invoice):
        """Add invoice line items with proper per-item tax categories."""
        currency = invoice.currency.code if invoice.currency else 'PEN'

        for i, item in enumerate(invoice.items.all(), 1):
            line = ET.SubElement(root, 'cac:InvoiceLine')
            line_id = ET.SubElement(line, 'cbc:ID')
            line_id.text = str(i)

            qty = ET.SubElement(line, 'cbc:InvoicedQuantity')
            qty.set('unitCode', item.unit.code if item.unit else 'NIU')
            qty.text = str(item.quantity)

            line_ext_amount = ET.SubElement(line, 'cbc:LineExtensionAmount')
            line_ext_amount.set('currencyID', currency)
            line_ext_amount.text = str(item.subtotal)

            # Pricing Reference
            pricing = ET.SubElement(line, 'cac:PricingReference')
            alt_price = ET.SubElement(pricing, 'cac:AlternativeConditionPrice')
            price_amount = ET.SubElement(alt_price, 'cbc:PriceAmount')
            price_amount.set('currencyID', currency)

            affectation = IGV_AFFECTATION.get(item.affectation_type, IGV_AFFECTATION['10'])
            if item.affectation_type == '10':
                unit_with_igv = item.unit_price * (Decimal('1') + affectation['rate'])
            else:
                unit_with_igv = item.unit_price
            price_amount.text = str(unit_with_igv.quantize(Decimal('0.01')))

            price_type = ET.SubElement(alt_price, 'cbc:PriceTypeCode')
            price_type.text = '01' if item.affectation_type != '21' else '02'

            # Tax per item
            item_tax = ET.SubElement(line, 'cac:TaxTotal')
            item_tax_amount = ET.SubElement(item_tax, 'cbc:TaxAmount')
            item_tax_amount.set('currencyID', currency)
            item_tax_amount.text = str(item.igv)

            item_tax_sub = ET.SubElement(item_tax, 'cac:TaxSubtotal')
            item_taxable = ET.SubElement(item_tax_sub, 'cbc:TaxableAmount')
            item_taxable.set('currencyID', currency)
            item_taxable.text = str(item.subtotal)

            item_tax_amt2 = ET.SubElement(item_tax_sub, 'cbc:TaxAmount')
            item_tax_amt2.set('currencyID', currency)
            item_tax_amt2.text = str(item.igv)

            item_cat = ET.SubElement(item_tax_sub, 'cac:TaxCategory')
            cat_id_elem = ET.SubElement(item_cat, 'cbc:ID')
            cat_id_elem.text = affectation['category']
            cat_pct = ET.SubElement(item_cat, 'cbc:Percent')
            cat_pct.text = str(affectation['rate'] * 100)
            cat_exempt = ET.SubElement(item_cat, 'cbc:TaxExemptionReasonCode')
            cat_exempt.text = item.affectation_type

            item_scheme = ET.SubElement(item_cat, 'cac:TaxScheme')
            is_id = ET.SubElement(item_scheme, 'cbc:ID')
            is_id.text = affectation['code']
            is_name = ET.SubElement(item_scheme, 'cbc:Name')
            is_name.text = 'IGV'
            is_code = ET.SubElement(item_scheme, 'cbc:TaxTypeCode')
            is_code.text = 'VAT'

            # Item description
            item_elem = ET.SubElement(line, 'cac:Item')
            desc = ET.SubElement(item_elem, 'cbc:Description')
            desc.text = item.description

            # Price (sin IGV)
            price_elem = ET.SubElement(line, 'cac:Price')
            price_val = ET.SubElement(price_elem, 'cbc:PriceAmount')
            price_val.set('currencyID', currency)
            price_val.text = str(item.unit_price)

    def build_invoice_xml(self, invoice):
        """Build UBL 2.1 XML for a Factura (01) or Boleta (03)."""
        from apps.core.models import Company
        company = Company.objects.first()
        if not company:
            raise ValueError("No se ha configurado la empresa")

        currency = invoice.currency.code if invoice.currency else 'PEN'
        root = ET.Element('Invoice', self._ns())

        # UBL Extensions (placeholder for digital signature)
        ext_content = ET.SubElement(root, 'ext:UBLExtensions')
        ext = ET.SubElement(ext_content, 'ext:UBLExtension')
        ET.SubElement(ext, 'ext:ExtensionContent')

        # UBL Version & Customization
        ET.SubElement(root, 'cbc:UBLVersionID').text = '2.1'
        ET.SubElement(root, 'cbc:CustomizationID').text = '2.0'

        # Document ID
        ET.SubElement(root, 'cbc:ID').text = f"{invoice.series}-{invoice.correlative:08d}"
        ET.SubElement(root, 'cbc:IssueDate').text = invoice.issue_date.strftime('%Y-%m-%d')

        type_code = ET.SubElement(root, 'cbc:InvoiceTypeCode')
        type_code.set('listID', '0101')
        type_code.text = invoice.doc_type

        ET.SubElement(root, 'cbc:DocumentCurrencyCode').text = currency

        # Amount in words
        if _flag_active('invoice_amount_in_words'):
            note = ET.SubElement(root, 'cbc:Note')
            note.set('languageLocaleID', '1000')
            note.text = amount_to_words(invoice.total)

        # Supplier & Customer
        self._add_supplier(root, company)
        self._add_customer(root, invoice.customer)

        # Payment Terms
        payment = ET.SubElement(root, 'cac:PaymentTerms')
        ET.SubElement(payment, 'cbc:ID').text = 'FormaPago'
        ET.SubElement(payment, 'cbc:PaymentMeansID').text = (
            'Contado' if invoice.payment_condition == 'cash' else 'Credito'
        )
        if invoice.payment_condition == 'credit' and invoice.due_date:
            ET.SubElement(payment, 'cbc:Amount').text = str(invoice.total)
            payment_due = ET.SubElement(root, 'cac:PaymentTerms')
            ET.SubElement(payment_due, 'cbc:ID').text = 'FormaPago'
            ET.SubElement(payment_due, 'cbc:PaymentMeansID').text = 'Cuota001'
            amt = ET.SubElement(payment_due, 'cbc:Amount')
            amt.set('currencyID', currency)
            amt.text = str(invoice.total)
            ET.SubElement(payment_due, 'cbc:PaymentDueDate').text = invoice.due_date.strftime('%Y-%m-%d')

        # Tax totals (properly split by affectation)
        self._add_tax_totals(root, invoice)

        # Legal Monetary Total
        monetary_total = ET.SubElement(root, 'cac:LegalMonetaryTotal')
        line_ext = ET.SubElement(monetary_total, 'cbc:LineExtensionAmount')
        line_ext.set('currencyID', currency)
        line_ext.text = str(invoice.op_gravada + invoice.op_exonerada + invoice.op_inafecta)

        tax_incl = ET.SubElement(monetary_total, 'cbc:TaxInclusiveAmount')
        tax_incl.set('currencyID', currency)
        tax_incl.text = str(invoice.total)

        if invoice.discount_total > 0:
            discount = ET.SubElement(monetary_total, 'cbc:AllowanceTotalAmount')
            discount.set('currencyID', currency)
            discount.text = str(invoice.discount_total)

        payable = ET.SubElement(monetary_total, 'cbc:PayableAmount')
        payable.set('currencyID', currency)
        payable.text = str(invoice.total)

        # Invoice Lines
        self._add_invoice_lines(root, invoice)

        xml_string = ET.tostring(root, encoding='unicode', xml_declaration=True)
        return xml_string

    def build_credit_note_xml(self, invoice):
        """Build UBL 2.1 XML for Nota de Credito (07)."""
        if not _flag_active('sunat_nota_credito_debito'):
            return self.build_invoice_xml(invoice)

        from apps.core.models import Company
        company = Company.objects.first()
        if not company:
            raise ValueError("No se ha configurado la empresa")

        currency = invoice.currency.code if invoice.currency else 'PEN'

        ns = self._ns()
        ns['xmlns'] = 'urn:oasis:names:specification:ubl:schema:xsd:CreditNote-2'
        root = ET.Element('CreditNote', ns)

        # UBL Extensions
        ext_content = ET.SubElement(root, 'ext:UBLExtensions')
        ext = ET.SubElement(ext_content, 'ext:UBLExtension')
        ET.SubElement(ext, 'ext:ExtensionContent')

        ET.SubElement(root, 'cbc:UBLVersionID').text = '2.1'
        ET.SubElement(root, 'cbc:CustomizationID').text = '2.0'
        ET.SubElement(root, 'cbc:ID').text = f"{invoice.series}-{invoice.correlative:08d}"
        ET.SubElement(root, 'cbc:IssueDate').text = invoice.issue_date.strftime('%Y-%m-%d')
        ET.SubElement(root, 'cbc:DocumentCurrencyCode').text = currency

        # DiscrepancyResponse (motivo de la nota)
        discrepancy = ET.SubElement(root, 'cac:DiscrepancyResponse')
        ET.SubElement(discrepancy, 'cbc:ReferenceID').text = (
            f"{invoice.related_series}-{invoice.related_correlative:08d}" if invoice.related_correlative else ''
        )
        ET.SubElement(discrepancy, 'cbc:ResponseCode').text = invoice.related_reason[:2] if invoice.related_reason else '01'
        ET.SubElement(discrepancy, 'cbc:Description').text = invoice.related_reason or 'Anulacion de la operacion'

        # BillingReference (documento original)
        billing_ref = ET.SubElement(root, 'cac:BillingReference')
        inv_doc_ref = ET.SubElement(billing_ref, 'cac:InvoiceDocumentReference')
        ET.SubElement(inv_doc_ref, 'cbc:ID').text = (
            f"{invoice.related_series}-{invoice.related_correlative:08d}" if invoice.related_correlative else ''
        )
        ET.SubElement(inv_doc_ref, 'cbc:DocumentTypeCode').text = invoice.related_doc_type or '01'

        self._add_supplier(root, company)
        self._add_customer(root, invoice.customer)
        self._add_tax_totals(root, invoice)

        # Legal Monetary Total
        monetary_total = ET.SubElement(root, 'cac:LegalMonetaryTotal')
        payable = ET.SubElement(monetary_total, 'cbc:PayableAmount')
        payable.set('currencyID', currency)
        payable.text = str(invoice.total)

        # Credit Note Lines (use CreditNoteLine instead of InvoiceLine)
        for i, item in enumerate(invoice.items.all(), 1):
            line = ET.SubElement(root, 'cac:CreditNoteLine')
            ET.SubElement(line, 'cbc:ID').text = str(i)
            qty = ET.SubElement(line, 'cbc:CreditedQuantity')
            qty.set('unitCode', item.unit.code if item.unit else 'NIU')
            qty.text = str(item.quantity)
            amt = ET.SubElement(line, 'cbc:LineExtensionAmount')
            amt.set('currencyID', currency)
            amt.text = str(item.subtotal)

            item_elem = ET.SubElement(line, 'cac:Item')
            ET.SubElement(item_elem, 'cbc:Description').text = item.description

            price_elem = ET.SubElement(line, 'cac:Price')
            pv = ET.SubElement(price_elem, 'cbc:PriceAmount')
            pv.set('currencyID', currency)
            pv.text = str(item.unit_price)

        return ET.tostring(root, encoding='unicode', xml_declaration=True)

    def build_debit_note_xml(self, invoice):
        """Build UBL 2.1 XML for Nota de Debito (08)."""
        if not _flag_active('sunat_nota_credito_debito'):
            return self.build_invoice_xml(invoice)

        from apps.core.models import Company
        company = Company.objects.first()
        if not company:
            raise ValueError("No se ha configurado la empresa")

        currency = invoice.currency.code if invoice.currency else 'PEN'

        ns = self._ns()
        ns['xmlns'] = 'urn:oasis:names:specification:ubl:schema:xsd:DebitNote-2'
        root = ET.Element('DebitNote', ns)

        ext_content = ET.SubElement(root, 'ext:UBLExtensions')
        ext = ET.SubElement(ext_content, 'ext:UBLExtension')
        ET.SubElement(ext, 'ext:ExtensionContent')

        ET.SubElement(root, 'cbc:UBLVersionID').text = '2.1'
        ET.SubElement(root, 'cbc:CustomizationID').text = '2.0'
        ET.SubElement(root, 'cbc:ID').text = f"{invoice.series}-{invoice.correlative:08d}"
        ET.SubElement(root, 'cbc:IssueDate').text = invoice.issue_date.strftime('%Y-%m-%d')
        ET.SubElement(root, 'cbc:DocumentCurrencyCode').text = currency

        discrepancy = ET.SubElement(root, 'cac:DiscrepancyResponse')
        ET.SubElement(discrepancy, 'cbc:ReferenceID').text = (
            f"{invoice.related_series}-{invoice.related_correlative:08d}" if invoice.related_correlative else ''
        )
        ET.SubElement(discrepancy, 'cbc:ResponseCode').text = invoice.related_reason[:2] if invoice.related_reason else '01'
        ET.SubElement(discrepancy, 'cbc:Description').text = invoice.related_reason or 'Intereses por mora'

        billing_ref = ET.SubElement(root, 'cac:BillingReference')
        inv_doc_ref = ET.SubElement(billing_ref, 'cac:InvoiceDocumentReference')
        ET.SubElement(inv_doc_ref, 'cbc:ID').text = (
            f"{invoice.related_series}-{invoice.related_correlative:08d}" if invoice.related_correlative else ''
        )
        ET.SubElement(inv_doc_ref, 'cbc:DocumentTypeCode').text = invoice.related_doc_type or '01'

        self._add_supplier(root, company)
        self._add_customer(root, invoice.customer)
        self._add_tax_totals(root, invoice)

        monetary_total = ET.SubElement(root, 'cac:RequestedMonetaryTotal')
        payable = ET.SubElement(monetary_total, 'cbc:PayableAmount')
        payable.set('currencyID', currency)
        payable.text = str(invoice.total)

        for i, item in enumerate(invoice.items.all(), 1):
            line = ET.SubElement(root, 'cac:DebitNoteLine')
            ET.SubElement(line, 'cbc:ID').text = str(i)
            qty = ET.SubElement(line, 'cbc:DebitedQuantity')
            qty.set('unitCode', item.unit.code if item.unit else 'NIU')
            qty.text = str(item.quantity)
            amt = ET.SubElement(line, 'cbc:LineExtensionAmount')
            amt.set('currencyID', currency)
            amt.text = str(item.subtotal)

            item_elem = ET.SubElement(line, 'cac:Item')
            ET.SubElement(item_elem, 'cbc:Description').text = item.description

            price_elem = ET.SubElement(line, 'cac:Price')
            pv = ET.SubElement(price_elem, 'cbc:PriceAmount')
            pv.set('currencyID', currency)
            pv.text = str(item.unit_price)

        return ET.tostring(root, encoding='unicode', xml_declaration=True)

    # ========================================================================
    # DIGITAL SIGNATURE
    # ========================================================================

    def sign_xml(self, xml_content):
        """Sign XML with digital certificate using xmlsec."""
        if not _flag_active('sunat_digital_signature'):
            return xml_content

        try:
            import lxml.etree as lxml_et
            import xmlsec

            from apps.core.models import Company
            company = Company.objects.first()
            if not company or not company.certificate:
                logger.warning("No digital certificate configured, skipping XML signing")
                return xml_content

            # Parse XML with lxml
            doc = lxml_et.fromstring(xml_content.encode('utf-8'))

            # Find ExtensionContent to place signature
            ns = {
                'ext': 'urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2',
            }
            ext_content = doc.find('.//ext:ExtensionContent', ns)
            if ext_content is None:
                logger.warning("ExtensionContent not found in XML, skipping signing")
                return xml_content

            # Create signature template
            sig_node = xmlsec.template.create(
                doc, xmlsec.Transform.EXCL_C14N, xmlsec.Transform.RSA_SHA1, ns_prefix='ds'
            )
            ext_content.append(sig_node)

            ref = xmlsec.template.add_reference(sig_node, xmlsec.Transform.SHA1, uri='')
            xmlsec.template.add_transform(ref, xmlsec.Transform.ENVELOPED)

            key_info = xmlsec.template.ensure_key_info(sig_node)
            xmlsec.template.add_x509_data(key_info)

            # Load certificate
            cert_path = company.certificate.path
            cert_password = company.certificate_password or ''

            ctx = xmlsec.SignatureContext()
            key = xmlsec.Key.from_file(cert_path, xmlsec.KeyFormat.PKCS12_PEM, password=cert_password)
            ctx.key = key

            ctx.sign(sig_node)

            return lxml_et.tostring(doc, xml_declaration=True, encoding='unicode')

        except ImportError:
            logger.error("xmlsec/lxml not available for XML signing")
            return xml_content
        except Exception as e:
            logger.error(f"Error signing XML: {e}")
            return xml_content

    # ========================================================================
    # QR CODE GENERATION
    # ========================================================================

    def generate_qr_data(self, invoice, hash_code):
        """Generate QR code data string per SUNAT format."""
        from apps.core.models import Company
        company = Company.objects.first()
        if not company:
            return ''

        # Format: RUC|TIPO|SERIE|CORRELATIVO|IGV|TOTAL|FECHA|TIPO_DOC_CLIENTE|NRO_DOC|HASH
        qr_string = '|'.join([
            company.ruc,
            invoice.doc_type,
            invoice.series,
            str(invoice.correlative),
            str(invoice.igv),
            str(invoice.total),
            invoice.issue_date.strftime('%Y-%m-%d'),
            SUNAT_IDENTITY_TYPES.get(invoice.customer.doc_type, '1'),
            invoice.customer.doc_number,
            hash_code,
        ])
        return qr_string

    def generate_qr_image(self, invoice, hash_code):
        """Generate QR code image as base64 PNG."""
        if not _flag_active('sunat_qr_code'):
            return ''

        try:
            import qrcode

            qr_data = self.generate_qr_data(invoice, hash_code)
            qr = qrcode.QRCode(version=1, box_size=4, border=2)
            qr.add_data(qr_data)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")

            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            return base64.b64encode(buffer.getvalue()).decode('utf-8')
        except ImportError:
            logger.error("qrcode library not available")
            return ''
        except Exception as e:
            logger.error(f"Error generating QR: {e}")
            return ''

    def generate_hash(self, xml_content):
        """Generate SHA-256 hash of XML content."""
        return hashlib.sha256(xml_content.encode()).hexdigest()

    # ========================================================================
    # SUNAT RESPONSE PARSING
    # ========================================================================

    def _parse_sunat_response(self, response_text):
        """Parse SUNAT SOAP response, extract status code and CDR."""
        if not _flag_active('sunat_response_parsing'):
            return {'code': '0', 'description': 'Parsing deshabilitado', 'cdr_content': None}

        try:
            root = ET.fromstring(response_text)

            # Find response code in SOAP body
            # SUNAT returns applicationResponse with ZIP containing CDR
            ns = {
                'soap': 'http://schemas.xmlsoap.org/soap/envelope/',
                'br': 'http://service.sunat.gob.pe',
            }

            # Check for SOAP fault
            fault = root.find('.//soap:Fault', ns)
            if fault is not None:
                fault_string = fault.findtext('faultstring', 'Error desconocido')
                fault_code = fault.findtext('faultcode', '9999')
                return {'code': fault_code, 'description': fault_string, 'cdr_content': None}

            # Extract applicationResponse (base64 ZIP with CDR)
            app_response = root.findtext('.//br:sendBillResponse/applicationResponse', '')
            if not app_response:
                app_response = root.findtext('.//applicationResponse', '')

            cdr_content = None
            response_code = '0'
            response_desc = 'Aceptado'

            if app_response:
                try:
                    zip_data = base64.b64decode(app_response)
                    with zipfile.ZipFile(io.BytesIO(zip_data)) as zf:
                        for name in zf.namelist():
                            if name.endswith('.xml'):
                                cdr_xml = zf.read(name)
                                cdr_content = cdr_xml

                                # Parse CDR for response code
                                cdr_root = ET.fromstring(cdr_xml)
                                resp_code = cdr_root.findtext('.//{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}ResponseCode', '0')
                                resp_desc = cdr_root.findtext('.//{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}Description', 'Aceptado')
                                response_code = resp_code
                                response_desc = resp_desc
                                break
                except Exception as e:
                    logger.error(f"Error parsing CDR ZIP: {e}")

            return {'code': response_code, 'description': response_desc, 'cdr_content': cdr_content}

        except ET.ParseError as e:
            logger.error(f"Error parsing SUNAT XML response: {e}")
            return {'code': '9999', 'description': f'Error parseando respuesta: {e}', 'cdr_content': None}

    # ========================================================================
    # SEND TO SUNAT
    # ========================================================================

    def send_invoice(self, invoice):
        """Send invoice to SUNAT (or beta environment)."""
        try:
            # Build appropriate XML based on doc type
            if invoice.doc_type == '07':
                xml_content = self.build_credit_note_xml(invoice)
            elif invoice.doc_type == '08':
                xml_content = self.build_debit_note_xml(invoice)
            else:
                xml_content = self.build_invoice_xml(invoice)

            # Sign XML if enabled
            xml_content = self.sign_xml(xml_content)

            hash_code = self.generate_hash(xml_content)

            # Generate QR if enabled
            qr_base64 = self.generate_qr_image(invoice, hash_code)

            # Generate amount in words if enabled
            words = amount_to_words(invoice.total)

            log_entry = SunatLog.objects.create(
                action=SunatLog.Action.SEND_INVOICE,
                document_type=invoice.doc_type,
                document_number=invoice.full_number,
                request_data={'xml_hash': hash_code},
            )

            # Save XML file
            xml_filename = f"{self.ruc}-{invoice.doc_type}-{invoice.full_number}.xml"
            invoice.xml_file.save(xml_filename, ContentFile(xml_content.encode('utf-8')), save=False)

            # In beta/development, simulate successful response
            if not self.production:
                invoice.status = 'accepted'
                invoice.sunat_response_code = '0'
                invoice.sunat_response_description = f'El comprobante fue aceptado (BETA)'
                invoice.hash_code = hash_code
                if qr_base64:
                    invoice.qr_code = qr_base64
                if words:
                    invoice.amount_in_words = words
                invoice.save()

                log_entry.success = True
                log_entry.response_code = '0'
                log_entry.response_data = {'message': 'Accepted in BETA mode', 'hash': hash_code}
                log_entry.save()

                return {'success': True, 'message': 'Comprobante aceptado (modo beta)'}

            # Production: send via SOAP to SUNAT
            # ZIP the XML
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
                zf.writestr(xml_filename, xml_content)
            zip_b64 = base64.b64encode(zip_buffer.getvalue()).decode('utf-8')

            soap_envelope = f"""<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                  xmlns:ser="http://service.sunat.gob.pe">
    <soapenv:Header>
        <wsse:Security xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd">
            <wsse:UsernameToken>
                <wsse:Username>{self.ruc}{self.user}</wsse:Username>
                <wsse:Password>{self.password}</wsse:Password>
            </wsse:UsernameToken>
        </wsse:Security>
    </soapenv:Header>
    <soapenv:Body>
        <ser:sendBill>
            <fileName>{xml_filename.replace('.xml', '.zip')}</fileName>
            <contentFile>{zip_b64}</contentFile>
        </ser:sendBill>
    </soapenv:Body>
</soapenv:Envelope>"""

            headers = {'Content-Type': 'text/xml; charset=utf-8', 'SOAPAction': ''}
            response = requests.post(self.base_url, data=soap_envelope.encode('utf-8'), headers=headers, timeout=30)

            # Parse response
            parsed = self._parse_sunat_response(response.text)

            invoice.hash_code = hash_code
            if qr_base64:
                invoice.qr_code = qr_base64
            if words:
                invoice.amount_in_words = words

            if response.status_code == 200 and parsed['code'] in ('0', ''):
                invoice.status = 'accepted'
                invoice.sunat_response_code = parsed['code']
                invoice.sunat_response_description = parsed['description']

                # Save CDR file
                if parsed.get('cdr_content'):
                    cdr_filename = f"R-{xml_filename}"
                    invoice.cdr_file.save(cdr_filename, ContentFile(parsed['cdr_content']), save=False)

                invoice.save()

                log_entry.success = True
                log_entry.response_code = parsed['code']
                log_entry.response_data = {'description': parsed['description']}
                log_entry.save()
                return {'success': True, 'message': f'Comprobante aceptado: {parsed["description"]}'}

            else:
                # Check if it's an observation (codes 100-1999 are warnings, still accepted)
                try:
                    code_int = int(parsed['code'])
                    if 100 <= code_int <= 1999:
                        invoice.status = 'accepted'
                    else:
                        invoice.status = 'rejected'
                except ValueError:
                    invoice.status = 'rejected'

                invoice.sunat_response_code = parsed['code']
                invoice.sunat_response_description = parsed['description']
                invoice.save()

                log_entry.success = invoice.status == 'accepted'
                log_entry.response_code = parsed['code']
                log_entry.error_message = parsed['description']
                log_entry.save()
                return {
                    'success': invoice.status == 'accepted',
                    'message': f"SUNAT [{parsed['code']}]: {parsed['description']}",
                }

        except Exception as e:
            logger.error(f"Error sending invoice to SUNAT: {e}")
            return {'success': False, 'message': str(e)}

    # ========================================================================
    # COMUNICACION DE BAJA
    # ========================================================================

    def build_voided_documents_xml(self, void_date, invoices_to_void):
        """Build XML for Comunicacion de Baja."""
        if not _flag_active('sunat_comunicacion_baja'):
            return None

        from apps.core.models import Company
        company = Company.objects.first()
        if not company:
            raise ValueError("No se ha configurado la empresa")

        ns = {
            'xmlns': 'urn:sunat:names:specification:ubl:peru:schema:xsd:VoidedDocuments-1',
            'xmlns:cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2',
            'xmlns:cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
            'xmlns:ext': 'urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2',
            'xmlns:sac': 'urn:sunat:names:specification:ubl:peru:schema:xsd:SunatAggregateComponents-1',
        }
        root = ET.Element('VoidedDocuments', ns)

        ext_content = ET.SubElement(root, 'ext:UBLExtensions')
        ext = ET.SubElement(ext_content, 'ext:UBLExtension')
        ET.SubElement(ext, 'ext:ExtensionContent')

        ET.SubElement(root, 'cbc:UBLVersionID').text = '2.0'
        ET.SubElement(root, 'cbc:CustomizationID').text = '1.0'

        # ID: RA-YYYYMMDD-NNNNN
        void_id = f"RA-{void_date.strftime('%Y%m%d')}-00001"
        ET.SubElement(root, 'cbc:ID').text = void_id
        ET.SubElement(root, 'cbc:ReferenceDate').text = void_date.strftime('%Y-%m-%d')
        ET.SubElement(root, 'cbc:IssueDate').text = void_date.strftime('%Y-%m-%d')

        # Supplier
        supplier = ET.SubElement(root, 'cac:AccountingSupplierParty')
        party = ET.SubElement(supplier, 'cac:Party')
        party_id = ET.SubElement(party, 'cac:PartyIdentification')
        pid = ET.SubElement(party_id, 'cbc:ID')
        pid.set('schemeID', '6')
        pid.text = company.ruc
        party_legal = ET.SubElement(party, 'cac:PartyLegalEntity')
        ET.SubElement(party_legal, 'cbc:RegistrationName').text = company.name

        # Voided lines
        for i, inv in enumerate(invoices_to_void, 1):
            line = ET.SubElement(root, 'sac:VoidedDocumentsLine')
            ET.SubElement(line, 'cbc:LineID').text = str(i)
            ET.SubElement(line, 'cbc:DocumentTypeCode').text = inv.doc_type
            ET.SubElement(line, 'sac:DocumentSerialID').text = inv.series
            ET.SubElement(line, 'sac:DocumentNumberID').text = str(inv.correlative)
            ET.SubElement(line, 'sac:VoidReasonDescription').text = inv.notes or 'Anulacion de comprobante'

        return ET.tostring(root, encoding='unicode', xml_declaration=True)

    def send_voided_documents(self, void_date, invoices_to_void):
        """Send Comunicacion de Baja to SUNAT."""
        if not _flag_active('sunat_comunicacion_baja'):
            return {'success': False, 'message': 'Feature deshabilitada: sunat_comunicacion_baja'}

        try:
            xml_content = self.build_voided_documents_xml(void_date, invoices_to_void)
            if not xml_content:
                return {'success': False, 'message': 'Error generando XML de baja'}

            xml_content = self.sign_xml(xml_content)

            log_entry = SunatLog.objects.create(
                action=SunatLog.Action.VOID,
                document_number=f"RA-{void_date.strftime('%Y%m%d')}",
                request_data={'count': len(invoices_to_void)},
            )

            if not self.production:
                for inv in invoices_to_void:
                    inv.status = 'voided'
                    inv.save(update_fields=['status'])
                log_entry.success = True
                log_entry.response_code = '0'
                log_entry.save()
                return {'success': True, 'message': 'Comunicacion de Baja procesada (BETA)'}

            # Production: use sendSummary endpoint
            filename = f"{self.ruc}-RA-{void_date.strftime('%Y%m%d')}-00001.xml"
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
                zf.writestr(filename, xml_content)
            zip_b64 = base64.b64encode(zip_buffer.getvalue()).decode('utf-8')

            soap_envelope = f"""<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                  xmlns:ser="http://service.sunat.gob.pe">
    <soapenv:Header>
        <wsse:Security xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd">
            <wsse:UsernameToken>
                <wsse:Username>{self.ruc}{self.user}</wsse:Username>
                <wsse:Password>{self.password}</wsse:Password>
            </wsse:UsernameToken>
        </wsse:Security>
    </soapenv:Header>
    <soapenv:Body>
        <ser:sendSummary>
            <fileName>{filename.replace('.xml', '.zip')}</fileName>
            <contentFile>{zip_b64}</contentFile>
        </ser:sendSummary>
    </soapenv:Body>
</soapenv:Envelope>"""

            headers = {'Content-Type': 'text/xml; charset=utf-8', 'SOAPAction': ''}
            response = requests.post(self.base_url, data=soap_envelope.encode('utf-8'), headers=headers, timeout=30)

            if response.status_code == 200:
                # Extract ticket number
                ticket = ''
                try:
                    resp_root = ET.fromstring(response.text)
                    ticket = resp_root.findtext('.//ticket', '')
                except Exception:
                    pass

                for inv in invoices_to_void:
                    inv.status = 'voided'
                    inv.sunat_ticket = ticket
                    inv.save(update_fields=['status', 'sunat_ticket'])

                log_entry.success = True
                log_entry.response_code = '0'
                log_entry.response_data = {'ticket': ticket}
                log_entry.save()
                return {'success': True, 'message': f'Comunicacion de Baja enviada. Ticket: {ticket}'}

            log_entry.success = False
            log_entry.error_message = response.text[:500]
            log_entry.save()
            return {'success': False, 'message': f'Error SUNAT: {response.status_code}'}

        except Exception as e:
            logger.error(f"Error sending voided documents: {e}")
            return {'success': False, 'message': str(e)}

    # ========================================================================
    # RESUMEN DIARIO
    # ========================================================================

    def build_summary_documents_xml(self, summary_date, boletas):
        """Build XML for Resumen Diario de Boletas."""
        if not _flag_active('sunat_resumen_diario'):
            return None

        from apps.core.models import Company
        company = Company.objects.first()
        if not company:
            raise ValueError("No se ha configurado la empresa")

        ns = {
            'xmlns': 'urn:sunat:names:specification:ubl:peru:schema:xsd:SummaryDocuments-1',
            'xmlns:cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2',
            'xmlns:cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
            'xmlns:ext': 'urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2',
            'xmlns:sac': 'urn:sunat:names:specification:ubl:peru:schema:xsd:SunatAggregateComponents-1',
        }
        root = ET.Element('SummaryDocuments', ns)

        ext_content = ET.SubElement(root, 'ext:UBLExtensions')
        ext = ET.SubElement(ext_content, 'ext:UBLExtension')
        ET.SubElement(ext, 'ext:ExtensionContent')

        ET.SubElement(root, 'cbc:UBLVersionID').text = '2.0'
        ET.SubElement(root, 'cbc:CustomizationID').text = '1.1'

        summary_id = f"RC-{summary_date.strftime('%Y%m%d')}-00001"
        ET.SubElement(root, 'cbc:ID').text = summary_id
        ET.SubElement(root, 'cbc:ReferenceDate').text = summary_date.strftime('%Y-%m-%d')
        ET.SubElement(root, 'cbc:IssueDate').text = summary_date.strftime('%Y-%m-%d')

        supplier = ET.SubElement(root, 'cac:AccountingSupplierParty')
        party = ET.SubElement(supplier, 'cac:Party')
        party_id = ET.SubElement(party, 'cac:PartyIdentification')
        pid = ET.SubElement(party_id, 'cbc:ID')
        pid.set('schemeID', '6')
        pid.text = company.ruc
        party_legal = ET.SubElement(party, 'cac:PartyLegalEntity')
        ET.SubElement(party_legal, 'cbc:RegistrationName').text = company.name

        for i, boleta in enumerate(boletas, 1):
            line = ET.SubElement(root, 'sac:SummaryDocumentsLine')
            ET.SubElement(line, 'cbc:LineID').text = str(i)
            ET.SubElement(line, 'cbc:DocumentTypeCode').text = '03'
            ET.SubElement(line, 'cbc:ID').text = boleta.full_number

            cust_ref = ET.SubElement(line, 'cac:AccountingCustomerParty')
            cust_party = ET.SubElement(cust_ref, 'cac:Party')
            cust_legal = ET.SubElement(cust_party, 'cac:PartyLegalEntity')
            ET.SubElement(cust_legal, 'cbc:RegistrationName').text = boleta.customer.name

            status = ET.SubElement(line, 'cac:Status')
            ET.SubElement(status, 'cbc:ConditionCode').text = '1'  # 1=Adicionar

            total_amount = ET.SubElement(line, 'sac:TotalAmount')
            total_amount.set('currencyID', 'PEN')
            total_amount.text = str(boleta.total)

            # Billing payment
            billing = ET.SubElement(line, 'sac:BillingPayment')
            paid = ET.SubElement(billing, 'cbc:PaidAmount')
            paid.set('currencyID', 'PEN')
            paid.text = str(boleta.op_gravada)
            ET.SubElement(billing, 'cbc:InstructionID').text = '01'

            if boleta.op_exonerada > 0:
                billing2 = ET.SubElement(line, 'sac:BillingPayment')
                paid2 = ET.SubElement(billing2, 'cbc:PaidAmount')
                paid2.set('currencyID', 'PEN')
                paid2.text = str(boleta.op_exonerada)
                ET.SubElement(billing2, 'cbc:InstructionID').text = '02'

            # Tax total
            tax_total = ET.SubElement(line, 'cac:TaxTotal')
            tax_amt = ET.SubElement(tax_total, 'cbc:TaxAmount')
            tax_amt.set('currencyID', 'PEN')
            tax_amt.text = str(boleta.igv)

            tax_sub = ET.SubElement(tax_total, 'cac:TaxSubtotal')
            sub_amt = ET.SubElement(tax_sub, 'cbc:TaxAmount')
            sub_amt.set('currencyID', 'PEN')
            sub_amt.text = str(boleta.igv)
            cat = ET.SubElement(tax_sub, 'cac:TaxCategory')
            scheme = ET.SubElement(cat, 'cac:TaxScheme')
            ET.SubElement(scheme, 'cbc:ID').text = '1000'
            ET.SubElement(scheme, 'cbc:Name').text = 'IGV'
            ET.SubElement(scheme, 'cbc:TaxTypeCode').text = 'VAT'

        return ET.tostring(root, encoding='unicode', xml_declaration=True)

    def send_daily_summary(self, summary_date, boletas):
        """Send Resumen Diario to SUNAT."""
        if not _flag_active('sunat_resumen_diario'):
            return {'success': False, 'message': 'Feature deshabilitada: sunat_resumen_diario'}

        try:
            xml_content = self.build_summary_documents_xml(summary_date, boletas)
            if not xml_content:
                return {'success': False, 'message': 'Error generando XML de resumen'}

            xml_content = self.sign_xml(xml_content)

            log_entry = SunatLog.objects.create(
                action=SunatLog.Action.SEND_INVOICE,
                document_type='RC',
                document_number=f"RC-{summary_date.strftime('%Y%m%d')}",
                request_data={'count': len(boletas)},
            )

            if not self.production:
                log_entry.success = True
                log_entry.response_code = '0'
                log_entry.save()
                return {'success': True, 'message': f'Resumen Diario procesado (BETA) - {len(boletas)} boletas'}

            filename = f"{self.ruc}-RC-{summary_date.strftime('%Y%m%d')}-00001.xml"
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
                zf.writestr(filename, xml_content)
            zip_b64 = base64.b64encode(zip_buffer.getvalue()).decode('utf-8')

            soap_envelope = f"""<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                  xmlns:ser="http://service.sunat.gob.pe">
    <soapenv:Header>
        <wsse:Security xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd">
            <wsse:UsernameToken>
                <wsse:Username>{self.ruc}{self.user}</wsse:Username>
                <wsse:Password>{self.password}</wsse:Password>
            </wsse:UsernameToken>
        </wsse:Security>
    </soapenv:Header>
    <soapenv:Body>
        <ser:sendSummary>
            <fileName>{filename.replace('.xml', '.zip')}</fileName>
            <contentFile>{zip_b64}</contentFile>
        </ser:sendSummary>
    </soapenv:Body>
</soapenv:Envelope>"""

            headers = {'Content-Type': 'text/xml; charset=utf-8', 'SOAPAction': ''}
            response = requests.post(self.base_url, data=soap_envelope.encode('utf-8'), headers=headers, timeout=30)

            if response.status_code == 200:
                ticket = ''
                try:
                    resp_root = ET.fromstring(response.text)
                    ticket = resp_root.findtext('.//ticket', '')
                except Exception:
                    pass
                log_entry.success = True
                log_entry.response_code = '0'
                log_entry.response_data = {'ticket': ticket}
                log_entry.save()
                return {'success': True, 'message': f'Resumen Diario enviado. Ticket: {ticket}'}

            log_entry.success = False
            log_entry.error_message = response.text[:500]
            log_entry.save()
            return {'success': False, 'message': f'Error SUNAT: {response.status_code}'}

        except Exception as e:
            logger.error(f"Error sending daily summary: {e}")
            return {'success': False, 'message': str(e)}

    # ========================================================================
    # GUIA DE REMISION ELECTRONICA (GRE)
    # ========================================================================

    def build_dispatch_guide_xml(self, guide):
        """Build UBL 2.1 XML for Guia de Remision Electronica."""
        if not _flag_active('sunat_gre'):
            return None

        from apps.core.models import Company
        company = Company.objects.first()
        if not company:
            raise ValueError("No se ha configurado la empresa")

        ns = {
            'xmlns': 'urn:oasis:names:specification:ubl:schema:xsd:DespatchAdvice-2',
            'xmlns:cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2',
            'xmlns:cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
            'xmlns:ext': 'urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2',
        }
        root = ET.Element('DespatchAdvice', ns)

        ext_content = ET.SubElement(root, 'ext:UBLExtensions')
        ext = ET.SubElement(ext_content, 'ext:UBLExtension')
        ET.SubElement(ext, 'ext:ExtensionContent')

        ET.SubElement(root, 'cbc:UBLVersionID').text = '2.1'
        ET.SubElement(root, 'cbc:CustomizationID').text = '2.0'
        ET.SubElement(root, 'cbc:ID').text = guide.full_number
        ET.SubElement(root, 'cbc:IssueDate').text = guide.issue_date.strftime('%Y-%m-%d')

        # Despatch advice type (09=Remitente, 31=Transportista)
        type_code = ET.SubElement(root, 'cbc:DespatchAdviceTypeCode')
        type_code.text = '09' if guide.guide_type == 'remitente' else '31'

        if guide.description:
            ET.SubElement(root, 'cbc:Note').text = guide.description

        # Related document
        if guide.related_invoice:
            add_doc = ET.SubElement(root, 'cac:AdditionalDocumentReference')
            ET.SubElement(add_doc, 'cbc:ID').text = guide.related_invoice.full_number
            ET.SubElement(add_doc, 'cbc:DocumentTypeCode').text = guide.related_invoice.doc_type

        # Supplier
        supplier = ET.SubElement(root, 'cac:DespatchSupplierParty')
        party = ET.SubElement(supplier, 'cac:Party')
        party_id = ET.SubElement(party, 'cac:PartyIdentification')
        pid = ET.SubElement(party_id, 'cbc:ID')
        pid.set('schemeID', '6')
        pid.text = company.ruc
        party_legal = ET.SubElement(party, 'cac:PartyLegalEntity')
        ET.SubElement(party_legal, 'cbc:RegistrationName').text = company.name

        # Recipient
        if guide.recipient:
            delivery_party = ET.SubElement(root, 'cac:DeliveryCustomerParty')
            dparty = ET.SubElement(delivery_party, 'cac:Party')
            dparty_id = ET.SubElement(dparty, 'cac:PartyIdentification')
            dpid = ET.SubElement(dparty_id, 'cbc:ID')
            dpid.set('schemeID', SUNAT_IDENTITY_TYPES.get(guide.recipient.doc_type, '6'))
            dpid.text = guide.recipient.doc_number
            dparty_legal = ET.SubElement(dparty, 'cac:PartyLegalEntity')
            ET.SubElement(dparty_legal, 'cbc:RegistrationName').text = guide.recipient.name

        # Shipment
        shipment = ET.SubElement(root, 'cac:Shipment')
        ET.SubElement(shipment, 'cbc:ID').text = '1'
        ET.SubElement(shipment, 'cbc:HandlingCode').text = (
            '01' if guide.transfer_reason == 'sale' else
            '02' if guide.transfer_reason == 'purchase' else
            '04' if guide.transfer_reason == 'transfer' else '01'
        )
        ET.SubElement(shipment, 'cbc:HandlingInstructions').text = guide.get_transfer_reason_display()

        gross = ET.SubElement(shipment, 'cbc:GrossWeightMeasure')
        gross.set('unitCode', 'KGM')
        gross.text = str(guide.gross_weight)
        ET.SubElement(shipment, 'cbc:TotalTransportHandlingUnitQuantity').text = str(guide.packages)

        # Transfer start date
        shipment_stage = ET.SubElement(shipment, 'cac:ShipmentStage')
        transport_event = ET.SubElement(shipment_stage, 'cac:TransportEvent')
        ET.SubElement(transport_event, 'cbc:OccurrenceDate').text = guide.transfer_start_date.strftime('%Y-%m-%d')

        # Carrier
        if guide.carrier_ruc:
            carrier = ET.SubElement(shipment_stage, 'cac:CarrierParty')
            c_party = ET.SubElement(carrier, 'cac:Party')
            c_id = ET.SubElement(c_party, 'cac:PartyIdentification')
            cid = ET.SubElement(c_id, 'cbc:ID')
            cid.set('schemeID', '6')
            cid.text = guide.carrier_ruc
            c_name = ET.SubElement(c_party, 'cac:PartyName')
            ET.SubElement(c_name, 'cbc:Name').text = guide.carrier_name

        # Driver
        if guide.driver_license:
            driver = ET.SubElement(shipment_stage, 'cac:DriverPerson')
            ET.SubElement(driver, 'cbc:ID').text = guide.driver_license
            ET.SubElement(driver, 'cbc:FirstName').text = guide.driver_name

        # Vehicle
        if guide.vehicle_plate:
            transport = ET.SubElement(shipment_stage, 'cac:TransportMeans')
            road_transport = ET.SubElement(transport, 'cac:RoadTransport')
            ET.SubElement(road_transport, 'cbc:LicensePlateID').text = guide.vehicle_plate

        # Origin/Destination
        delivery = ET.SubElement(shipment, 'cac:Delivery')
        delivery_addr = ET.SubElement(delivery, 'cac:DeliveryAddress')
        ET.SubElement(delivery_addr, 'cbc:ID').text = guide.destination_ubigeo or '150101'
        ET.SubElement(delivery_addr, 'cbc:StreetName').text = guide.destination_address

        origin = ET.SubElement(shipment, 'cac:OriginAddress')
        ET.SubElement(origin, 'cbc:ID').text = guide.origin_ubigeo or '150101'
        ET.SubElement(origin, 'cbc:StreetName').text = guide.origin_address

        # Items
        for i, item in enumerate(guide.items.all(), 1):
            line = ET.SubElement(root, 'cac:DespatchLine')
            ET.SubElement(line, 'cbc:ID').text = str(i)
            qty = ET.SubElement(line, 'cbc:DeliveredQuantity')
            qty.set('unitCode', item.unit.code if item.unit else 'NIU')
            qty.text = str(item.quantity)

            item_elem = ET.SubElement(line, 'cac:Item')
            ET.SubElement(item_elem, 'cbc:Description').text = item.description

        return ET.tostring(root, encoding='unicode', xml_declaration=True)

    # ========================================================================
    # PDF GENERATION
    # ========================================================================

    def generate_invoice_pdf(self, invoice):
        """Generate PDF for invoice using ReportLab."""
        if not _flag_active('invoice_pdf_generation'):
            return None

        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.units import mm
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as RLImage
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

            from apps.core.models import Company
            company = Company.objects.first()

            buffer = io.BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=15*mm, rightMargin=15*mm, topMargin=15*mm, bottomMargin=15*mm)
            styles = getSampleStyleSheet()
            elements = []

            # Header style
            header_style = ParagraphStyle('Header', parent=styles['Normal'], fontSize=8, leading=10)
            title_style = ParagraphStyle('Title2', parent=styles['Normal'], fontSize=12, leading=14, alignment=1, spaceAfter=6)
            small_style = ParagraphStyle('Small', parent=styles['Normal'], fontSize=7, leading=9)

            # Company info + Document type header
            doc_type_name = SUNAT_DOC_TYPES.get(invoice.doc_type, 'COMPROBANTE')
            elements.append(Paragraph(f"<b>{company.name if company else 'NexusERP'}</b>", title_style))
            if company:
                elements.append(Paragraph(f"RUC: {company.ruc}", ParagraphStyle('center', parent=header_style, alignment=1)))
                elements.append(Paragraph(f"{company.address}", ParagraphStyle('center', parent=header_style, alignment=1)))
            elements.append(Spacer(1, 4*mm))

            elements.append(Paragraph(f"<b>{doc_type_name.upper()} ELECTRONICA</b>", ParagraphStyle('doctype', parent=styles['Normal'], fontSize=14, alignment=1, textColor=colors.HexColor('#6366f1'))))
            elements.append(Paragraph(f"<b>{invoice.full_number}</b>", ParagraphStyle('docnum', parent=styles['Normal'], fontSize=11, alignment=1)))
            elements.append(Spacer(1, 4*mm))

            # Customer info table
            customer_data = [
                ['Cliente:', invoice.customer.name, 'Fecha:', invoice.issue_date.strftime('%d/%m/%Y')],
                ['RUC/DNI:', invoice.customer.doc_number, 'Moneda:', invoice.currency.code if invoice.currency else 'PEN'],
                ['Condicion:', invoice.get_payment_condition_display(), 'Vencimiento:', invoice.due_date.strftime('%d/%m/%Y') if invoice.due_date else '-'],
            ]
            ct = Table(customer_data, colWidths=[55, 200, 55, 100])
            ct.setStyle(TableStyle([
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ]))
            elements.append(ct)
            elements.append(Spacer(1, 4*mm))

            # Items table
            items_header = ['#', 'Descripcion', 'Und', 'Cant.', 'P. Unit.', 'Desc.', 'IGV', 'Total']
            items_data = [items_header]
            for i, item in enumerate(invoice.items.all(), 1):
                items_data.append([
                    str(i), item.description,
                    item.unit.code if item.unit else 'NIU',
                    f"{item.quantity:.2f}", f"{item.unit_price:.2f}",
                    f"{item.discount:.2f}", f"{item.igv:.2f}", f"{item.total:.2f}",
                ])

            it = Table(items_data, colWidths=[20, 170, 30, 40, 50, 40, 40, 50])
            it.setStyle(TableStyle([
                ('FONTSIZE', (0, 0), (-1, -1), 7),
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#6366f1')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
                ('ALIGN', (2, 1), (-1, -1), 'RIGHT'),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                ('TOPPADDING', (0, 0), (-1, -1), 3),
            ]))
            elements.append(it)
            elements.append(Spacer(1, 4*mm))

            # Totals
            totals_data = []
            if invoice.op_gravada > 0:
                totals_data.append(['Op. Gravada:', f"S/ {invoice.op_gravada:.2f}"])
            if invoice.op_exonerada > 0:
                totals_data.append(['Op. Exonerada:', f"S/ {invoice.op_exonerada:.2f}"])
            if invoice.op_inafecta > 0:
                totals_data.append(['Op. Inafecta:', f"S/ {invoice.op_inafecta:.2f}"])
            if invoice.discount_total > 0:
                totals_data.append(['Descuento:', f"S/ {invoice.discount_total:.2f}"])
            totals_data.append(['IGV (18%):', f"S/ {invoice.igv:.2f}"])
            totals_data.append(['TOTAL:', f"S/ {invoice.total:.2f}"])

            tt = Table(totals_data, colWidths=[100, 80], hAlign='RIGHT')
            tt.setStyle(TableStyle([
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
                ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
                ('LINEABOVE', (0, -1), (-1, -1), 1, colors.HexColor('#6366f1')),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ]))
            elements.append(tt)
            elements.append(Spacer(1, 3*mm))

            # Amount in words
            if invoice.amount_in_words:
                elements.append(Paragraph(f"<i>{invoice.amount_in_words}</i>", small_style))
                elements.append(Spacer(1, 3*mm))

            # QR Code
            if invoice.qr_code:
                try:
                    qr_data = base64.b64decode(invoice.qr_code)
                    qr_img = RLImage(io.BytesIO(qr_data), width=25*mm, height=25*mm)
                    elements.append(qr_img)
                except Exception:
                    pass

            # Hash
            if invoice.hash_code:
                elements.append(Paragraph(f"Hash: {invoice.hash_code[:20]}...", small_style))

            doc.build(elements)
            return buffer.getvalue()

        except ImportError:
            logger.error("reportlab not available for PDF generation")
            return None
        except Exception as e:
            logger.error(f"Error generating PDF: {e}")
            return None

    # ========================================================================
    # EXISTING METHODS (kept)
    # ========================================================================

    def consult_ruc(self, ruc_number):
        """Consult RUC information from SUNAT."""
        try:
            url = f"{settings.SUNAT_CONFIG['CONSULT_RUC_URL']}"
            params = {'numero': ruc_number}
            response = requests.get(url, params=params, timeout=10)

            log_entry = SunatLog.objects.create(
                action=SunatLog.Action.CONSULT_RUC,
                document_number=ruc_number,
                request_data=params,
            )

            if response.status_code == 200:
                data = response.json()
                log_entry.success = True
                log_entry.response_data = data
                log_entry.save()
                return {'success': True, 'data': data}
            else:
                log_entry.success = False
                log_entry.error_message = response.text
                log_entry.save()
                return {'success': False, 'message': 'RUC no encontrado'}

        except Exception as e:
            logger.error(f"Error consulting RUC: {e}")
            return {'success': False, 'message': str(e)}

    def get_exchange_rate(self):
        """Get current exchange rate from SUNAT."""
        try:
            url = settings.SUNAT_CONFIG['TIPO_CAMBIO_URL']
            response = requests.get(url, timeout=10)

            if response.status_code == 200:
                data = response.json()
                SunatLog.objects.create(
                    action=SunatLog.Action.EXCHANGE_RATE,
                    response_data=data,
                    success=True,
                )
                return {'success': True, 'data': data}
            return {'success': False, 'message': 'Error obteniendo tipo de cambio'}

        except Exception as e:
            logger.error(f"Error getting exchange rate: {e}")
            return {'success': False, 'message': str(e)}
