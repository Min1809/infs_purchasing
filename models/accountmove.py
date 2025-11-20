from odoo import models
import logging

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = 'account.move'

    def action_post(self):
        """Log values when posting account moves"""
        for move in self:
            _logger.info("="*80)
            _logger.info(f"POSTING MOVE - ID: {move.id}")
            _logger.info(f"  Name: {move.name}")
            _logger.info(f"  State: {move.state}")
            _logger.info(f"  Move Type: {move.move_type}")
            _logger.info(f"  Partner: {move.partner_id.name if move.partner_id else 'N/A'}")
            _logger.info(f"  Date: {move.date}")
            _logger.info(f"  Invoice Date: {move.invoice_date}")
            _logger.info(f"  Journal: {move.journal_id.name if move.journal_id else 'N/A'}")
            _logger.info(f"  Sequence Number: {move.sequence_number}")
            _logger.info(f"  Highest Name: {move.highest_name}")
            _logger.info(f"  Posted Before: {move.posted_before}")
            if hasattr(move, 'invoice_origin'):
                _logger.info(f"  Invoice Origin: {move.invoice_origin}")
            _logger.info("="*80)
        
        return super(AccountMove, self).action_post()

    def _post(self, soft=True):
        """Log values during internal post method"""
        for move in self:
            _logger.info("-"*80)
            _logger.info(f"_POST METHOD - ID: {move.id}")
            _logger.info(f"  Name before post: {move.name}")
            _logger.info(f"  State before post: {move.state}")
            _logger.info(f"  Sequence Number before post: {move.sequence_number}")
            _logger.info(f"  Soft: {soft}")
            _logger.info("-"*80)
        
        result = super(AccountMove, self)._post(soft=soft)
        
        for move in self:
            _logger.info("-"*80)
            _logger.info(f"_POST METHOD AFTER - ID: {move.id}")
            _logger.info(f"  Name after post: {move.name}")
            _logger.info(f"  State after post: {move.state}")
            _logger.info(f"  Sequence Number after post: {move.sequence_number}")
            _logger.info("-"*80)
        
        return result
