# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.tools.misc import frozendict


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    account_payable_split_id = fields.Many2one(
        "account.account",
        string="Account Payable Split",
        ondelete="restrict",
        copy=False,
        help="Account payable used when this payment term line was split by product.",
    )

    @api.depends("date_maturity", "discount_date", "account_payable_split_id")
    def _compute_term_key(self):
        super()._compute_term_key()
        for line in self.filtered(
            lambda record: record.display_type == "payment_term"
            and record.account_payable_split_id
        ):
            line.term_key = frozendict({
                "move_id": line.move_id.id,
                "date_maturity": fields.Date.to_date(line.date_maturity),
                "discount_date": line.discount_date,
                "account_payable_split_id": line.account_payable_split_id.id,
            })

    @api.depends("move_id", "product_id", "move_id.partner_id", "move_id.fiscal_position_id")
    def _compute_product_account_payable_id(self):
        for line in self:
            line.product_account_payable_id = line._get_account_payable_for_line()

    product_account_payable_id = fields.Many2one(
        "account.account",
        string="Account Payable",
        compute="_compute_product_account_payable_id",
        store=False,
    )

    def _get_account_payable_for_line(self):
        self.ensure_one()
        move = self.move_id
        if not move.is_purchase_document(include_receipts=True):
            return False
        if self.display_type == "product" and self.product_id:
            return self.product_id.product_tmpl_id._get_product_account_payable(
                partner=move.partner_id,
                fiscal_pos=move.fiscal_position_id,
            )
        return move.with_company(move.company_id).commercial_partner_id.property_account_payable_id

    def _compute_account_id(self):
        split_term_lines = self.filtered(
            lambda line: line.display_type == "payment_term"
            and line.account_payable_split_id
        )
        if split_term_lines:
            for line in split_term_lines:
                line.account_id = line.account_payable_split_id
        return super(AccountMoveLine, self - split_term_lines)._compute_account_id()
