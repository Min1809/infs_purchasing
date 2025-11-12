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
    ], default='draft', string='Approval Stage', tracking=True)

    # state = fields.Selection([
    #     ('draft', 'RFQ'),
    #     ('approved', 'Approved'),
    #     ('sent', 'RFQ Sent'),
    #     ('purchase', 'Purchase Order'),
    #     ('done', 'Locked'),
    #     ('cancel', 'Cancelled'),
    # ],
    # string='Status',
    # readonly=True,
    # copy=False,
    # index=True,
    # tracking=3,
    # default='draft')
    
    approval_status = fields.Char(string='Approval Status', compute='_compute_approval_status', store=True)

    @api.depends('approval_stage')
    def _compute_approval_status(self):
        for order in self:
            order.approval_status = dict(self._fields['approval_stage'].selection).get(order.approval_stage)
            
    def button_draft(self):
        res = super(PurchaseOrder, self).button_draft()
        self.approval_stage = 'draft'
        return res
    
    def button_cancel(self):
        res = super(PurchaseOrder, self).button_cancel()
        self.approval_stage = 'canceled'
        return res
    
    def button_confirm(self):
        if not self.approval_stage == 'approved':
            raise UserError(_("Purchase Order must be fully approved before confirmation. Current stage: %s") % self.approval_stage)
        else:
            self.approval_stage = 'confirmed'
            res = super(PurchaseOrder, self).button_confirm()
            return res

    def action_submit_rfq(self):
        if self.approval_stage == 'draft':
            self.approval_stage = 'submitted'
        _logger.info(f"RFQ {self.name} submitted for approval.")
        
    def check_approval_mail_status(self):
        status = self.env['ir.config_parameter'].sudo().get_param('send_approval_mails', 'False').strip().lower() == 'true'
        return status
    
    def check_stage_and_approve_after_confirmed(self):
        group_one = self.env.ref('infs_purchasing.purchase_supervisor_level_1')
        group_two = self.env.ref('infs_purchasing.purchase_supervisor_level_2')
        group_three = self.env.ref('infs_purchasing.purchase_supervisor_level_3')

        if self.approval_stage=="draft":
            if group_one.users:
                self.approval_stage = 'submitted'
                self._send_approval_notification()                
            else:
                _logger.info("No users in Level 1 group, auto-approving to 'approved'.")
        elif self.approval_stage=="submitted":
            if not group_two.users and not group_three.users:
                self.approval_stage = 'approved'
                # self.state = 'approved'
                self._send_approval_notification()
            else:
                self.approval_stage = 'approved_lvl_1'
                self._send_approval_notification()
        elif self.approval_stage == "approved_lvl_1":
            if not group_three.users:
                self.approval_stage = 'approved'
                # self.state = 'approved'
                self._send_approval_notification()
            else:
                self.approval_stage = 'approved_lvl_2'
                self._send_approval_notification()
        elif self.approval_stage == "approved_lvl_2":
            # self.approval_stage = 'approved'
            self._send_approval_notification()            
            
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
                self.state = 'approved'
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
                    # template.write({'email_to': email_to,'email_from': 'Infinity IT Group - CRM <crm@infinityitsuccess.com>',})
                    template.write({'email_to': email_to,'email_from': 'Min Pyae Sone - adMIN <minpyaesone.dev@gmail.com>',})
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
                        # template.write({'email_to': email_to,'email_from': 'Infinity IT Group - CRM <crm@infinityitsuccess.com>',})   
                        template.write({'email_to': email_to,'email_from': 'Min Pyae Sone - adMIN <minpyaesone.dev@gmail.com>',})
                        template.send_mail(order.id, force_send=True, raise_exception=True)
                        _logger.info(f"Email successfully sent to {order.user_id.partner_id.email}.")
                    else:
                        _logger.info(f"Approval mails are disabled. Not sending email for RFQ {order.name}.")
                except Exception as e:
                    _logger.error(f"Failed to send email for RFQ {order.name}. Error: {e}")
            
            
        