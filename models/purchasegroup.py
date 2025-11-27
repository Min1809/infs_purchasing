from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class PurchaseOrderGroupInherit(models.Model):
    _name = 'purchase.order.group'
    _inherit = ['purchase.order.group', 'mail.thread', 'mail.activity.mixin']
    
    approval_stage = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Pending L1 Approval'),
        ('approved_lvl_1', 'Pending L2 Approval'),
        ('approved_lvl_2', 'Pending Final Approval'),
        ('approved', 'Approved'),
        # ('confirmed', 'Confirmed'),
        ('canceled', 'Canceled'),
    ], string='Approval Stage', default='draft', tracking=True)
    
    approval_status = fields.Char(string='Approval Status', compute='_compute_approval_status')

    name = fields.Char(string='Group Reference', required=True, copy=False, readonly=True,
                       default='New')
    opportunity = fields.Many2one('crm.lead', string='Opportunity', compute='_compute_opportunity', 
                                   store=True, readonly=False, tracking=True)
    
    has_supervisor_2 = fields.Boolean(string='Has Level 2 Supervisor', compute='_compute_has_supervisor_2', default=False)
    has_supervisor_3 = fields.Boolean(string='Has Level 3 Supervisor', compute='_compute_has_supervisor_3', default=False)

    rfqs_sent = fields.Boolean(string='RFQs Sent', compute='_compute_rfqs_sent', default=False)

    @api.depends('order_ids.state')
    def _compute_rfqs_sent(self):
        for record in self:
            record.rfqs_sent = all(order.state in ['sent'] for order in record.order_ids) if record.order_ids else False

    @api.depends('approval_stage')
    def _compute_approval_status(self):
        for order in self:
            order.approval_status = dict(self.fields_get(allfields=['approval_stage'])['approval_stage']['selection']).get(order.approval_stage, 'Unknown')

    def write(self, vals):
        """
        Override write to call super normally.
        We prevent auto-deletion by overriding unlink instead.
        """
        return super(PurchaseOrderGroupInherit, self).write(vals)
    
    def unlink(self):
        """
        Override unlink to prevent automatic deletion by enterprise module.
        Only allow manual deletion through cancel workflow.
        """
        # Check if this is being called from our cancel workflow
        if not self._context.get('force_delete_group', False):
            # Prevent deletion - groups should only be deleted via cancel workflow
            _logger.info(f"Prevented auto-deletion of purchase group(s): {self.mapped('name')}")
            return True
        return super(PurchaseOrderGroupInherit, self).unlink()

    @api.depends('order_ids', 'order_ids.opportunity_id')
    def _compute_opportunity(self):
        for record in self:
            opportunities = record.order_ids.mapped('opportunity_id')
            if opportunities and len(opportunities) == 1:
                record.opportunity = opportunities[0]
            else:
                record.opportunity = False 

    @api.depends()
    def _compute_has_supervisor_2(self):
        group_two = self.env.ref('infs_purchasing.purchase_supervisor_level_2')
        for record in self:
            record.has_supervisor_2 = bool(group_two.users)
    
    @api.depends()
    def _compute_has_supervisor_3(self):
        group_three = self.env.ref('infs_purchasing.purchase_supervisor_level_3')
        for record in self:
            record.has_supervisor_3 = bool(group_three.users)
    
    priority = fields.Selection([
        ('0', 'Normal'),
        ('1', 'Urgent'),
    ], 'Priority', default='0')
    
    order_line_ids = fields.One2many(
        'purchase.order.line', 
        compute='_compute_order_line_ids',
        string='Order Lines'
    )
    
    @api.depends('order_ids', 'order_ids.order_line')
    def _compute_order_line_ids(self):
        """Compute all order lines from all purchase orders in this group"""
        for group in self:
            group.order_line_ids = group.order_ids.mapped('order_line').filtered(lambda l: not l.display_type)
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('purchase.order.group') or 'New'
        return super(PurchaseOrderGroupInherit, self).create(vals_list)
    
    def get_rfqgp_url(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        return f"{base_url}/web#id={self.id}&cids=1-2&menu_id=614&action=916&model=purchase.order.group&view_type=form"

    def get_ip_rfqgp_url(self):
        web_ip_url = self.env['ir.config_parameter'].sudo().get_param('website.ip_address')
        return f"{web_ip_url}/web#id={self.id}&cids=1-2&menu_id=614&action=916&model=purchase.order.group&view_type=form"
    
    def action_compare_order_lines(self):
        """Open a view to compare all order lines from purchase orders in this group"""
        self.ensure_one()
        ctx = dict(
            self.env.context,
            search_default_groupby_product=True,
        )
        view_id = self.env.ref('purchase_requisition.purchase_order_line_compare_tree').id
        return {
            'name': _('Compare Order Lines'),
            'type': 'ir.actions.act_window',
            'view_mode': 'list',
            'res_model': 'purchase.order.line',
            'views': [(view_id, "list")],
            'domain': [('order_id', 'in', self.order_ids.ids), ('display_type', '=', False)],
            'context': ctx,
        }
    
    def check_stage_and_approve_after_confirmed(self):
        group_one = self.env.ref('infs_purchasing.purchase_supervisor_level_1')
        group_two = self.env.ref('infs_purchasing.purchase_supervisor_level_2')
        group_three = self.env.ref('infs_purchasing.purchase_supervisor_level_3')        

        if self.approval_stage=="draft":
            if group_one.users:
                self.approval_stage = 'submitted'
                for record in self:
                    record.approval_stage = 'submitted'
                    for order in record.order_ids:
                        order._is_visible = False
                        order.state = 'sent'
                self._send_approval_notification()                
            else:
                raise UserError(_('No supervisor to approve this Purchase Order Group, please contact your administrator.'))
        elif self.approval_stage=="submitted":
            if not group_two.users and not group_three.users:
                self.approval_stage = 'approved'
                for record in self:
                    record.approval_stage = 'approved'
                self._send_approval_notification()
            else:
                self.approval_stage = 'approved_lvl_1'
                for record in self:
                    record.approval_stage = 'approved_lvl_1'
                self._send_approval_notification()
        elif self.approval_stage == "approved_lvl_1":
            if not group_three.users:
                self.approval_stage = 'approved'
                for record in self:
                    record.approval_stage = 'approved'
                self._send_approval_notification()
            else:
                self.approval_stage = 'approved_lvl_2'
                for record in self:
                    record.approval_stage = 'approved_lvl_2'
                self._send_approval_notification()
        elif self.approval_stage == "approved_lvl_2":
            self.approval_stage = 'approved'
            for record in self:
                record.approval_stage = 'approved'
                for order in record.order_ids:
                    order.is_approved = True
                    order._is_visible = True
            self._send_approval_notification()      

    def check_approval_mail_status(self):
        status = self.env['ir.config_parameter'].sudo().get_param('send_approval_mails', 'False').strip().lower() == 'true'
        return status

    def _send_approval_notification(self):
        for record in self:
            stage = record.approval_stage
            send_approval_mails = record.check_approval_mail_status()
            _logger.info(f"send_approval_mails: {send_approval_mails}")
            if send_approval_mails:
                _logger.info(f"Sending approval notification for stage: {stage}")
                if stage == 'submitted':
                    record._send_approval_email('infs_purchasing.email_template_rfqgp_level_1_approval', 'infs_purchasing.purchase_supervisor_level_1')
                elif stage == 'approved_lvl_1':
                    record._send_approval_email('infs_purchasing.email_template_rfqgp_level_2_approval', 'infs_purchasing.purchase_supervisor_level_2')
                elif stage == 'approved_lvl_2':
                    record._send_approval_email('infs_purchasing.email_template_rfqgp_level_3_approval', 'infs_purchasing.purchase_supervisor_level_3')
                elif stage == 'approved':
                    record.action_send_confirmed_mail_to_rfqgp()
                    _logger.info(f"Final approval email sent to the purchase order owner.")
            else:
                _logger.info(f"Approval mails are disabled. Not sending notification for stage: {stage}")

            

    def _send_approval_email(self, template_xml_id, mail_to_group):
        send_approval_mails = self.check_approval_mail_status()
        if send_approval_mails:
            mail_servers = self.env['ir.mail_server'].sudo().search([], limit=1)
            # _logger.info(f"Outgoing mail server found: {mail_servers[0].name}")
            if not mail_servers:
                _logger.warning("No outgoing mail server configured. Skipping email sending.")
                return
            else:
                _logger.info(f"Not Skipping?")
                template = self.env.ref(template_xml_id)
                email_to = self.get_email_to(mail_to_group)
                if email_to:
                    template.write({'email_to': email_to,'email_from': 'Infinity IT Group - CRM <crm@infinityitsuccess.com>',})
                    # template.write({'email_to': email_to,'email_from': 'Min Pyae Sone - adMIN <minpyaesone.dev@gmail.com>',})
                    for order in self:
                        _logger.info(f"Attempting to send testing email for{order.name}.")
                        _logger.info(f"This is self {self.id}.")
                    template.send_mail(self.id, force_send=True, raise_exception=True)
                else:
                    _logger.warning("No email addresses found for sending approval email.")
        else:
            _logger.info(f"Approval mails are disabled. Not sending email.")

    @api.model
    def get_email_to(self,mail_to_group):
        user_group = self.env.ref(mail_to_group)        
        email_list = [
            usr.partner_id.email for usr in user_group.users if usr.partner_id.email
        ]
        return ",".join(email_list) 
            
    def action_send_confirmed_mail_to_rfqgp(self):
        _logger.info(f"Preparing to send confirmed email to RFQ Group owner for RFQ Group {self.name}.")
        send_approval_mails = self.check_approval_mail_status()

        template = self.env.ref('infs_purchasing.email_template_rfqgp_approved')
        for order in self:
            if not order.create_uid or not order.create_uid.partner_id.email:
                _logger.error(f"RFQ Group {order.name} has no user email. Skipping.")
                continue
            
            else:
                email_to = order.create_uid.partner_id.email        
                _logger.info(f"Email to be sent to: {email_to}")    
                try:
                    if send_approval_mails:
                        _logger.info(f"Attempting to send email to {order.create_uid.partner_id.email} for RFQ Group {order.name}.")         
                        template.write({'email_to': email_to,'email_from': 'Infinity IT Group - CRM <crm@infinityitsuccess.com>',})   
                        # template.write({'email_to': email_to,'email_from': 'Min Pyae Sone - adMIN <minpyaesone.dev@gmail.com>',})
                        template.send_mail(order.id, force_send=True, raise_exception=True)
                        _logger.info(f"Email successfully sent to {order.create_uid.partner_id.email}.")
                    else:
                        _logger.info(f"Approval mails are disabled. Not sending email for RFQ Group {order.name}.")
                except Exception as e:
                    _logger.error(f"Failed to send email for RFQ Group {order.name}. Error: {e}")
    
    def action_confirm(self):
        """Confirm the purchase order group"""
        for record in self:
            if record.approval_stage != 'approved':
                raise UserError(_('Only approved groups can be confirmed.'))
            for order in record.order_ids:
                # Use the proper confirmation method instead of directly setting state
                if order.state in ('draft', 'sent'):
                    order.button_confirm()
                _logger.info(f"Confirming Purchase Order {order.name} in Group {record.name} , current state {order.state}, email {order.create_uid.partner_id.email if order.create_uid and order.create_uid.partner_id else 'No email'}")
            # record.approval_stage = 'confirmed'
    
    def action_cancel(self):
        """Cancel the purchase order group - shows wizard if any PO is already purchased"""
        self.ensure_one()
        
        # Check if any purchase order in the group has posted vendor bills
        has_vendor_bill = any(
            order.invoice_ids.filtered(lambda inv: inv.state == 'posted')
            for order in self.order_ids
        )
        
        if has_vendor_bill:
            # Show wizard for vendor bill warning
            return {
                'name': _('Cannot Cancel Purchase Order Group'),
                'type': 'ir.actions.act_window',
                'res_model': 'purchase.group.cancel.wizard',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_message': _('One of the PO from this compare group has a vendor bill. Please cancel it first in order to cancel this compare group.'),
                    'default_group_id': self.id,
                    'default_show_cancel_button': False,
                }
            }
        
        # Check if any purchase order in the group has state 'purchase'
        has_purchased_po = any(order.state == 'purchase' for order in self.order_ids)
        
        if has_purchased_po:
            # Show confirmation wizard
            return {
                'name': _('Cancel Purchase Order Group'),
                'type': 'ir.actions.act_window',
                'res_model': 'purchase.group.cancel.wizard',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_message': _('One of the RFQ from this compare group is already purchased. Do you really want to cancel this compare group?'),
                    'default_group_id': self.id,
                    'default_show_cancel_button': True,
                }
            }
        else:
            # Proceed with cancellation directly
            self._do_cancel()
    
    def _do_cancel(self):
        """Internal method to perform the actual cancellation"""
        for record in self:
            record.approval_stage = 'canceled'            
            for order in record.order_ids:
                order.state = 'cancel'
                order.is_approved = False
                _logger.info(f"Cancelling Purchase Order {order.name} in Group {record.name} , current state {order.state}, email {order.create_uid.partner_id.email if order.create_uid and order.create_uid.partner_id else 'No email'}.")
    
    def action_reset_to_draft(self):
        """Reset to draft"""
        for record in self:
            record.approval_stage = 'draft'
            for order in record.order_ids:
                order.state = 'draft'
                _logger.info(f"Resetting to draft Purchase Order {order.name} in Group {record.name} , current state {order.state}, email {order.create_uid.partner_id.email if order.create_uid and order.create_uid.partner_id else 'No email'}")

