from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)

class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    delay_supplier = fields.Integer(
        'Days of Delay',
        help="Lead time in days as defined by the supplier for this product.",
        default=0,
        tracking=True
    )
    
    product_display_name = fields.Char(
        string='Product Group',
        compute='_compute_product_display_name',
        store=False
    )
    
    @api.depends('product_id')
    def _compute_product_display_name(self):
        for line in self:
            line.product_display_name = line.product_id.display_name if line.product_id else ''

    @api.onchange('product_id', 'order_id.partner_id')
    def _onchange_product_id_set_delay_supplier(self):
        for line in self:
            # Only process if we have both product and partner
            if not line.product_id or not line.order_id.partner_id:
                line.delay_supplier = 0
                continue
            
            # Search for supplierinfo with the correct product and partner
            supplierinfo = self.env['product.supplierinfo'].search([
                ('product_tmpl_id', '=', line.product_id.product_tmpl_id.id),
                ('partner_id', '=', line.order_id.partner_id.id)
            ], limit=1)
            
            if supplierinfo:
                line.delay_supplier = supplierinfo.delay
                _logger.info(f"Set delay_supplier to {supplierinfo.delay} days for product {line.product_id.name} and partner {line.order_id.partner_id.name}")
            else:
                line.delay_supplier = 0
                _logger.warning(f"No supplierinfo found for product {line.product_id.name} and partner {line.order_id.partner_id.name}")

    @api.model
    def create(self, vals):
        record = super(PurchaseOrderLine, self).create(vals)
        # Trigger onchange after record is created
        record._onchange_product_id_set_delay_supplier()
        return record
    
    def write(self, vals):
        res = super(PurchaseOrderLine, self).write(vals)
        # Trigger onchange if product or order changes
        if 'product_id' in vals or 'order_id' in vals:
            self._onchange_product_id_set_delay_supplier()
        return res