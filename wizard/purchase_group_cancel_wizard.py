from odoo import models, fields, api, _

class PurchaseGroupCancelWizard(models.TransientModel):
    _name = 'purchase.group.cancel.wizard'
    _description = 'Purchase Group Cancel Confirmation Wizard'
    
    message = fields.Text(string='Message', readonly=True)
    group_id = fields.Many2one('purchase.order.group', string='Purchase Order Group', required=True)
    show_cancel_button = fields.Boolean(string='Show Cancel Button', default=True)
    
    def action_confirm_cancel(self):
        """Proceed with canceling the purchase order group"""
        self.ensure_one()
        if self.group_id:
            self.group_id._do_cancel()
        return {'type': 'ir.actions.act_window_close'}
    
    def action_go_back(self):
        """Close the wizard without doing anything"""
        return {'type': 'ir.actions.act_window_close'}
