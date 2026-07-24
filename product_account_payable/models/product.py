# -*- coding: utf-8 -*-

from odoo import fields, models

ACCOUNT_PAYABLE_DOMAIN = "[('account_type', '=', 'liability_payable'), ('active', '=', True)]"


class ProductCategory(models.Model):
    _inherit = "product.category"

    property_account_payable_categ_id = fields.Many2one(
        "account.account",
        company_dependent=True,
        string="Account Payable",
        domain=ACCOUNT_PAYABLE_DOMAIN,
        ondelete="restrict",
        help="Account payable used for vendor bills containing products in this category.",
    )


class ProductTemplate(models.Model):
    _inherit = "product.template"

    property_account_payable_id = fields.Many2one(
        "account.account",
        company_dependent=True,
        string="Account Payable",
        domain=ACCOUNT_PAYABLE_DOMAIN,
        ondelete="restrict",
        help="Account payable used for vendor bills containing this product. "
        "Falls back to the category, then the vendor account payable.",
    )

    def _get_product_account_payable(self, partner=None, fiscal_pos=None):
        self.ensure_one()
        company = self.company_id or self.env.company
        account = (
            self.property_account_payable_id
            or self.categ_id.property_account_payable_categ_id
        )
        if not account and partner:
            account = partner.with_company(company).property_account_payable_id
        if not account:
            account = company.partner_id.with_company(company).property_account_payable_id
        if fiscal_pos and account:
            account = fiscal_pos.map_account(account)
        return account
