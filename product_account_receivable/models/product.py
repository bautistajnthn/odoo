# -*- coding: utf-8 -*-

from odoo import fields, models

ACCOUNT_RECEIVABLE_DOMAIN = "[('account_type', '=', 'asset_receivable'), ('active', '=', True)]"


class ProductCategory(models.Model):
    _inherit = "product.category"

    property_account_receivable_categ_id = fields.Many2one(
        "account.account",
        company_dependent=True,
        string="Account Receivable",
        domain=ACCOUNT_RECEIVABLE_DOMAIN,
        ondelete="restrict",
        help="Account receivable used for customer invoices containing products in this category.",
    )


class ProductTemplate(models.Model):
    _inherit = "product.template"

    property_account_receivable_id = fields.Many2one(
        "account.account",
        company_dependent=True,
        string="Account Receivable",
        domain=ACCOUNT_RECEIVABLE_DOMAIN,
        ondelete="restrict",
        help="Account receivable used for customer invoices containing this product. "
        "Falls back to the category, then the customer account receivable.",
    )

    def _get_product_account_receivable(self, partner=None, fiscal_pos=None):
        self.ensure_one()
        company = self.company_id or self.env.company
        account = (
            self.property_account_receivable_id
            or self.categ_id.property_account_receivable_categ_id
        )
        if not account and partner:
            account = partner.with_company(company).property_account_receivable_id
        if not account:
            account = company.partner_id.with_company(company).property_account_receivable_id
        if fiscal_pos and account:
            account = fiscal_pos.map_account(account)
        return account
