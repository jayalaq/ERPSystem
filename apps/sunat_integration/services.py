"""
SUNAT Integration Services.
Handles electronic invoicing (facturación electrónica) with SUNAT Peru.
"""
import hashlib
import logging
import requests
from decimal import Decimal
from xml.etree import ElementTree as ET

from django.conf import settings

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
    '10': {'name': 'Gravado', 'code': '1000', 'rate': Decimal('0.18')},
    '20': {'name': 'Exonerado', 'code': '9997', 'rate': Decimal('0')},
    '30': {'name': 'Inafecto', 'code': '9998', 'rate': Decimal('0')},
    '21': {'name': 'Gratuito', 'code': '9996', 'rate': Decimal('0')},
}


class SunatService:
    """Service class for SUNAT electronic invoicing operations."""

    def __init__(self):
        config = settings.SUNAT_CONFIG
        self.ruc = config['RUC']
        self.user = config['USER']
        self.password = config['PASSWORD']
        self.production = config['PRODUCTION']
        self.base_url = config['PRODUCTION_URL'] if self.production else config['BETA_URL']

    def build_invoice_xml(self, invoice):
        """Build UBL 2.1 XML for an invoice."""
        from apps.core.models import Company
        company = Company.objects.first()
        if not company:
            raise ValueError("No se ha configurado la empresa")

        namespaces = {
            'xmlns': 'urn:oasis:names:specification:ubl:schema:xsd:Invoice-2',
            'xmlns:cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2',
            'xmlns:cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
            'xmlns:ext': 'urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2',
            'xmlns:ds': 'http://www.w3.org/2000/09/xmldsig#',
        }

        root = ET.Element('Invoice', namespaces)

        # UBL Extensions (for digital signature)
        ext_content = ET.SubElement(root, 'ext:UBLExtensions')
        ext = ET.SubElement(ext_content, 'ext:UBLExtension')
        ET.SubElement(ext, 'ext:ExtensionContent')

        # UBL Version
        ubl_version = ET.SubElement(root, 'cbc:UBLVersionID')
        ubl_version.text = '2.1'

        # Customization
        custom = ET.SubElement(root, 'cbc:CustomizationID')
        custom.text = '2.0'

        # Document ID
        doc_id = ET.SubElement(root, 'cbc:ID')
        doc_id.text = f"{invoice.series}-{invoice.correlative:08d}"

        # Issue Date
        issue = ET.SubElement(root, 'cbc:IssueDate')
        issue.text = invoice.issue_date.strftime('%Y-%m-%d')

        # Invoice Type Code
        type_code = ET.SubElement(root, 'cbc:InvoiceTypeCode')
        type_code.set('listID', '0101')
        type_code.text = invoice.doc_type

        # Currency
        currency = ET.SubElement(root, 'cbc:DocumentCurrencyCode')
        currency.text = 'PEN'

        # Supplier (Emisor)
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

        # Customer (Adquiriente)
        customer_party = ET.SubElement(root, 'cac:AccountingCustomerParty')
        cparty = ET.SubElement(customer_party, 'cac:Party')

        cparty_id = ET.SubElement(cparty, 'cac:PartyIdentification')
        cpid = ET.SubElement(cparty_id, 'cbc:ID')
        cpid.set('schemeID', SUNAT_IDENTITY_TYPES.get(invoice.customer.doc_type, '1'))
        cpid.text = invoice.customer.doc_number

        cparty_legal = ET.SubElement(cparty, 'cac:PartyLegalEntity')
        creg_name = ET.SubElement(cparty_legal, 'cbc:RegistrationName')
        creg_name.text = invoice.customer.name

        # Tax Totals
        tax_total = ET.SubElement(root, 'cac:TaxTotal')
        tax_amount = ET.SubElement(tax_total, 'cbc:TaxAmount')
        tax_amount.set('currencyID', 'PEN')
        tax_amount.text = str(invoice.igv)

        tax_subtotal = ET.SubElement(tax_total, 'cac:TaxSubtotal')
        taxable_amount = ET.SubElement(tax_subtotal, 'cbc:TaxableAmount')
        taxable_amount.set('currencyID', 'PEN')
        taxable_amount.text = str(invoice.op_gravada)

        sub_tax_amount = ET.SubElement(tax_subtotal, 'cbc:TaxAmount')
        sub_tax_amount.set('currencyID', 'PEN')
        sub_tax_amount.text = str(invoice.igv)

        tax_category = ET.SubElement(tax_subtotal, 'cac:TaxCategory')
        tax_scheme = ET.SubElement(tax_category, 'cac:TaxScheme')
        ts_id = ET.SubElement(tax_scheme, 'cbc:ID')
        ts_id.text = '1000'
        ts_name = ET.SubElement(tax_scheme, 'cbc:Name')
        ts_name.text = 'IGV'
        ts_code = ET.SubElement(tax_scheme, 'cbc:TaxTypeCode')
        ts_code.text = 'VAT'

        # Legal Monetary Total
        monetary_total = ET.SubElement(root, 'cac:LegalMonetaryTotal')
        line_ext = ET.SubElement(monetary_total, 'cbc:LineExtensionAmount')
        line_ext.set('currencyID', 'PEN')
        line_ext.text = str(invoice.op_gravada + invoice.op_exonerada + invoice.op_inafecta)

        tax_incl = ET.SubElement(monetary_total, 'cbc:TaxInclusiveAmount')
        tax_incl.set('currencyID', 'PEN')
        tax_incl.text = str(invoice.total)

        payable = ET.SubElement(monetary_total, 'cbc:PayableAmount')
        payable.set('currencyID', 'PEN')
        payable.text = str(invoice.total)

        # Invoice Lines
        for i, item in enumerate(invoice.items.all(), 1):
            line = ET.SubElement(root, 'cac:InvoiceLine')
            line_id = ET.SubElement(line, 'cbc:ID')
            line_id.text = str(i)

            qty = ET.SubElement(line, 'cbc:InvoicedQuantity')
            qty.set('unitCode', item.unit.code if item.unit else 'NIU')
            qty.text = str(item.quantity)

            line_ext_amount = ET.SubElement(line, 'cbc:LineExtensionAmount')
            line_ext_amount.set('currencyID', 'PEN')
            line_ext_amount.text = str(item.subtotal)

            # Pricing
            pricing = ET.SubElement(line, 'cac:PricingReference')
            alt_price = ET.SubElement(pricing, 'cac:AlternativeConditionPrice')
            price_amount = ET.SubElement(alt_price, 'cbc:PriceAmount')
            price_amount.set('currencyID', 'PEN')
            unit_with_igv = item.unit_price * Decimal('1.18') if item.affectation_type == '10' else item.unit_price
            price_amount.text = str(round(unit_with_igv, 2))
            price_type = ET.SubElement(alt_price, 'cbc:PriceTypeCode')
            price_type.text = '01'

            # Tax
            item_tax = ET.SubElement(line, 'cac:TaxTotal')
            item_tax_amount = ET.SubElement(item_tax, 'cbc:TaxAmount')
            item_tax_amount.set('currencyID', 'PEN')
            item_tax_amount.text = str(item.igv)

            item_tax_sub = ET.SubElement(item_tax, 'cac:TaxSubtotal')
            item_taxable = ET.SubElement(item_tax_sub, 'cbc:TaxableAmount')
            item_taxable.set('currencyID', 'PEN')
            item_taxable.text = str(item.subtotal)

            item_tax_amt2 = ET.SubElement(item_tax_sub, 'cbc:TaxAmount')
            item_tax_amt2.set('currencyID', 'PEN')
            item_tax_amt2.text = str(item.igv)

            item_cat = ET.SubElement(item_tax_sub, 'cac:TaxCategory')
            cat_id = ET.SubElement(item_cat, 'cbc:ID')
            cat_id.text = 'S'
            cat_pct = ET.SubElement(item_cat, 'cbc:Percent')
            affectation = IGV_AFFECTATION.get(item.affectation_type, IGV_AFFECTATION['10'])
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

            # Price
            price_elem = ET.SubElement(line, 'cac:Price')
            price_val = ET.SubElement(price_elem, 'cbc:PriceAmount')
            price_val.set('currencyID', 'PEN')
            price_val.text = str(item.unit_price)

        xml_string = ET.tostring(root, encoding='unicode', xml_declaration=True)
        return xml_string

    def generate_hash(self, xml_content):
        """Generate hash for QR code."""
        return hashlib.sha256(xml_content.encode()).hexdigest()

    def send_invoice(self, invoice):
        """Send invoice to SUNAT (or beta environment)."""
        try:
            xml_content = self.build_invoice_xml(invoice)
            hash_code = self.generate_hash(xml_content)

            log_entry = SunatLog.objects.create(
                action=SunatLog.Action.SEND_INVOICE,
                document_type=invoice.doc_type,
                document_number=invoice.full_number,
                request_data={'xml_hash': hash_code},
            )

            # In beta/development, simulate successful response
            if not self.production:
                invoice.status = 'accepted'
                invoice.sunat_response_code = '0'
                invoice.sunat_response_description = 'La Factura fue aceptada (BETA)'
                invoice.hash_code = hash_code
                invoice.save()

                log_entry.success = True
                log_entry.response_code = '0'
                log_entry.response_data = {'message': 'Accepted in BETA mode'}
                log_entry.save()

                return {'success': True, 'message': 'Comprobante aceptado (modo beta)'}

            # Production: send via SOAP to SUNAT
            filename = f"{self.ruc}-{invoice.doc_type}-{invoice.full_number}.xml"

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
                        <fileName>{filename}</fileName>
                        <contentFile>{xml_content}</contentFile>
                    </ser:sendBill>
                </soapenv:Body>
            </soapenv:Envelope>"""

            headers = {'Content-Type': 'text/xml; charset=utf-8', 'SOAPAction': ''}
            response = requests.post(self.base_url, data=soap_envelope, headers=headers, timeout=30)

            if response.status_code == 200:
                invoice.status = 'accepted'
                invoice.sunat_response_code = '0'
                invoice.hash_code = hash_code
                invoice.save()

                log_entry.success = True
                log_entry.response_code = '0'
                log_entry.save()
                return {'success': True, 'message': 'Comprobante enviado exitosamente'}
            else:
                invoice.status = 'rejected'
                invoice.sunat_response_code = str(response.status_code)
                invoice.sunat_response_description = response.text[:500]
                invoice.save()

                log_entry.success = False
                log_entry.response_code = str(response.status_code)
                log_entry.error_message = response.text[:1000]
                log_entry.save()
                return {'success': False, 'message': f'Error SUNAT: {response.status_code}'}

        except Exception as e:
            logger.error(f"Error sending invoice to SUNAT: {e}")
            return {'success': False, 'message': str(e)}

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
