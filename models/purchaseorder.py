from odoo import models, fields, api, _
from odoo.exceptions import UserError
import math
import logging

_logger = logging.getLogger(__name__)

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    approval_stage = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Pending L1 Approval'), 
        ('approved_lvl_1', 'Pending L2 Approval'), 
        ('approved_lvl_2', 'Pending Final Approval'), 
        ('approved', 'Approved'), 
        ('confirmed', 'Confirmed'), 
        ('canceled', 'Canceled'),
    ], string='Approval Stage', compute='_compute_approval_stage', store=True, readonly=False, tracking=True)
    
    approval_status = fields.Char(string='Approval Status', compute='_compute_approval_status', store=True)

    _is_visible = fields.Boolean(string="Is Visible", store=True, default=True)

    is_approved = fields.Boolean(string="Is Approved", default=False, store=True)

    _is_inherit = fields.Boolean(string="Has group", compute='_compute_is_inherit', store=True)

    has_zero_qty_lines = fields.Boolean(string="Has Zero Qty Lines", compute='_compute_has_zero_qty_lines')

    @api.depends('order_line', 'order_line.product_qty')
    def _compute_has_zero_qty_lines(self):
        for order in self:
            order.has_zero_qty_lines = any(line.product_qty == 0 for line in order.order_line)

    @api.depends('purchase_group_id')
    def _compute_is_inherit(self):
        for order in self:
            if order.purchase_group_id:
                order._is_inherit = True
                if order.is_approved:
                    order._is_visible = True
                else:
                    order._is_visible = False
            else:
                order._is_inherit = False
                order._is_visible = True


    @api.depends('purchase_group_id', 'purchase_group_id.approval_stage', 'is_approved')
    # @api.depends('purchase_group_id', 'is_approved')
    def _compute_approval_stage(self):
        for order in self:
            if not order.is_approved:
                gp_id = order.purchase_group_id
                gp_stage = gp_id.approval_stage if gp_id else None
                if gp_id and gp_stage != 'approved':
                    order.approval_stage = gp_stage
                elif gp_id and gp_stage == 'approved':
                    order.is_approved = True
                    order.approval_stage = gp_stage
                elif not order.approval_stage:
                    order.approval_stage = 'draft'
            # else:
            #     order.approval_stage = order.approval_stage

    @api.depends('approval_stage')
    def _compute_approval_status(self):
        for order in self:
            if order.purchase_group_id:
                _logger.info(f"Purchase Order Group found for PO {order.purchase_group_id}")
            order.approval_status = dict(self._fields['approval_stage'].selection).get(order.approval_stage)
            
    def button_draft(self):
        res = super(PurchaseOrder, self).button_draft()
        if self.is_approved or not self.purchase_group_id:
            self.approval_stage = 'draft'
            self._is_visible = True
        elif not self.is_approved and self.purchase_group_id:
            raise UserError(_("Cannot set to draft, please reset to draft the related RFQ Group first."))
        else:
            raise UserError(_("Cannot set to draft when not approved, please cancel the related RFQ Group first."))
        return res
    
    def button_cancel(self):
        res = super(PurchaseOrder, self).button_cancel()
        if self.is_approved or not self.purchase_group_id:
            self.approval_stage = 'canceled'
            self._is_visible = True
        else:            
            raise UserError(_("Cannot set to cancel when not approved, please cancel the related RFQ Group first."))
        return res
    
    def button_confirm(self):
        res = super(PurchaseOrder, self).button_confirm()
        self.approval_stage = 'confirmed'
        return res
    
    def action_rfq_send(self):
        result = super(PurchaseOrder, self).action_rfq_send()
        if self.purchase_group_id:
            # Set all RFQs in the same group to 'sent' state
            for order in self.purchase_group_id.order_ids:
                if order.state == 'draft':
                    order.state = 'sent'
        return result

    def action_submit_rfq(self):
        if self.approval_stage == 'draft':
            if self.purchase_group_id:
                self._is_visible = False
                self.purchase_group_id.approval_stage = 'submitted'
            else:
                self.approval_stage = 'submitted'
        
    def check_approval_mail_status(self):
        status = self.env['ir.config_parameter'].sudo().get_param('send_approval_mails', 'False').strip().lower() == 'true'
        return status
    
    def check_stage_and_approve_after_confirmed(self):
        group_one = self.env.ref('infs_purchasing.purchase_supervisor_level_1')
        group_two = self.env.ref('infs_purchasing.purchase_supervisor_level_2')
        group_three = self.env.ref('infs_purchasing.purchase_supervisor_level_3')        

        if not self.purchase_group_id or self.is_approved:
            if self.approval_stage=="draft":
                if group_one.users:                    
                    self.approval_stage = 'submitted'
                    # self.is_approved = False
                    self._is_visible = True
                    self._send_approval_notification()
                else:
                    _logger.info("No users in Level 1 group, auto-approving to 'approved'.")
            elif self.approval_stage=="submitted":
                if not group_two.users and not group_three.users:
                    self.approval_stage = 'approved'
                    self._send_approval_notification()
                else:
                    self.approval_stage = 'approved_lvl_1'
                    self._send_approval_notification()
            elif self.approval_stage == "approved_lvl_1":
                if not group_three.users:
                    self.approval_stage = 'approved'
                    self._send_approval_notification()
                else:
                    self.approval_stage = 'approved_lvl_2'
                    self._send_approval_notification()
            elif self.approval_stage == "approved_lvl_2":
                self.approval_stage = 'approved'
                self._send_approval_notification()
        else:
            raise UserError(_('Cannot submit/approve RFQ if the RFQ Group is not approved. Please get the RFQ Group approved first.'))
            
    def _send_approval_notification(self):
        stage = self.approval_stage
        send_approval_mails = self.check_approval_mail_status()
        _logger.info(f"send_approval_mails: {send_approval_mails}")
        if send_approval_mails:
            _logger.info(f"Sending approval notification for stage: {stage}")
            if stage == 'submitted':
                self._send_approval_email('infs_purchasing.email_template_rfqlevel_1_approval', 'infs_purchasing.purchase_supervisor_level_1')
            elif stage == 'approved_lvl_1':
                self._send_approval_email('infs_purchasing.email_template_rfqlevel_2_approval', 'infs_purchasing.purchase_supervisor_level_2')
            elif stage == 'approved_lvl_2':
                self._send_approval_email('infs_purchasing.email_template_rfqlevel_3_approval', 'infs_purchasing.purchase_supervisor_level_3')
            elif stage == 'approved':
                self.action_send_confirmed_mail_to_rfq()
                _logger.info(f"Final approval email sent to the purchase order owner.")
        else:
            _logger.info(f"Approval mails are disabled. Not sending notification for stage: {stage}")
            
            
    # Mailing
    
    def get_rfq_url(self, company):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        return f"{base_url}/web#id={self.id}&model=purchase.order&view_type=form&cids={company.id}"

    def get_ip_rfq_url(self, company):

        web_ip_url = self.env['ir.config_parameter'].sudo().get_param('website.ip_address')
        return f"{web_ip_url}/web#id={self.id}&model=purchase.order&view_type=form&cids={company.id}"
    
    @api.model
    def get_email_to(self,mail_to_group):
        user_group = self.env.ref(mail_to_group)        
        email_list = [
            usr.partner_id.email for usr in user_group.users if usr.partner_id.email
        ]
        return ",".join(email_list)    

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
            
    def action_send_confirmed_mail_to_rfq(self):
        _logger.info(f"Preparing to send confirmed email to RFQ owner for RFQ {self.name}.")
        send_approval_mails = self.check_approval_mail_status()

        template = self.env.ref('infs_purchasing.email_template_rfq_approved')
        for order in self:
            if not order.user_id or not order.user_id.partner_id.email:
                _logger.error(f"RFQ {order.name} has no user email. Skipping.")
                continue
            
            else:
                email_to = order.user_id.partner_id.email        
                _logger.info(f"Email to be sent to: {email_to}")    
                try:
                    if send_approval_mails:
                        _logger.info(f"Attempting to send email to {order.user_id.partner_id.email} for RFQ {order.name}.")         
                        template.write({'email_to': email_to,'email_from': 'Infinity IT Group - CRM <crm@infinityitsuccess.com>',})   
                        # template.write({'email_to': email_to,'email_from': 'Min Pyae Sone - adMIN <minpyaesone.dev@gmail.com>',})
                        template.send_mail(order.id, force_send=True, raise_exception=True)
                        _logger.info(f"Email successfully sent to {order.user_id.partner_id.email}.")
                    else:
                        _logger.info(f"Approval mails are disabled. Not sending email for RFQ {order.name}.")
                except Exception as e:
                    _logger.error(f"Failed to send email for RFQ {order.name}. Error: {e}")
    
    def action_clear_zero_qty_lines(self):
        """Remove purchase order lines with 0 product_qty"""
        for order in self:
            zero_qty_lines = order.order_line.filtered(lambda line: line.product_qty == 0)
            if zero_qty_lines:
                _logger.info(f"Removing {len(zero_qty_lines)} lines with 0 quantity from PO {order.name}.")
                zero_qty_lines.unlink()
            else:
                _logger.info(f"No lines with 0 quantity found in PO {order.name}.")
            
            
        