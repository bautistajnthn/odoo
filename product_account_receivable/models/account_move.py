# -*- coding: utf-8 -*-

from collections import defaultdict

from odoo import api, fields, models
from odoo.tools.misc import frozendict


class AccountMove(models.Model):
    _inherit = "account.move"

    product_account_receivable_summary = fields.Text(
        string="Account Receivable Summary",
        compute="_compute_product_account_receivable_summary",
    )

    @api.depends(
        "invoice_line_ids",
        "invoice_line_ids.product_id",
        "invoice_line_ids.price_subtotal",
        "amount_total_in_currency_signed",
        "amount_total_signed",
        "partner_id",
        "fiscal_position_id",
    )
    def _compute_product_account_receivable_summary(self):
        for move in self:
            if not move.is_sale_document(include_receipts=True):
                move.product_account_receivable_summary = False
                continue
            amounts = move._get_account_receivable_amounts_by_product()
            if not amounts:
                move.product_account_receivable_summary = False
                continue
            account_model = self.env["account.account"]
            parts = []
            for account_id, values in amounts.items():
                account = account_model.browse(account_id)
                amount = values["amount_currency"]
                parts.append(f"{account.display_name}: {move.currency_id.format(amount)}")
            move.product_account_receivable_summary = "\n".join(parts)

    def _get_account_receivable_amounts_by_product(self):
        self.ensure_one()
        if not self.is_invoice(include_receipts=True):
            return {}

        product_lines = self.invoice_line_ids.filtered(
            lambda line: line.display_type == "product" and line.product_id
        )
        subtotal_by_account = defaultdict(float)
        for line in product_lines:
            account = line._get_account_receivable_for_line()
            if not account:
                continue
            subtotal_by_account[account.id] += line.price_subtotal

        if not subtotal_by_account:
            return {}

        total_untaxed = sum(subtotal_by_account.values())
        if not total_untaxed:
            return {}

        total_currency = self.amount_total_in_currency_signed
        total_balance = self.amount_total_signed
        account_ids = list(subtotal_by_account.keys())
        amounts = {}
        running_currency = 0.0
        running_balance = 0.0

        for index, account_id in enumerate(account_ids):
            ratio = subtotal_by_account[account_id] / total_untaxed
            if index == len(account_ids) - 1:
                amount_currency = total_currency - running_currency
                balance = total_balance - running_balance
            else:
                amount_currency = self.currency_id.round(total_currency * ratio)
                balance = self.company_currency_id.round(total_balance * ratio)
                running_currency += amount_currency
                running_balance += balance
            amounts[account_id] = {
                "amount_currency": amount_currency,
                "balance": balance,
            }
        return amounts

    def _should_split_account_receivable_by_product(self):
        self.ensure_one()
        amounts = self._get_account_receivable_amounts_by_product()
        if len(amounts) > 1:
            return True
        if len(amounts) == 1:
            account_id = next(iter(amounts))
            partner_account = self.with_company(
                self.company_id
            ).commercial_partner_id.property_account_receivable_id
            return bool(partner_account and partner_account.id != account_id)
        return False

    def _build_product_account_receivable_needed_terms(self):
        self.ensure_one()
        AccountTax = self.env["account.tax"]
        amounts_by_account = self._get_account_receivable_amounts_by_product()
        needed_terms = {}
        sign = 1 if self.is_inbound(include_receipts=True) else -1
        total_currency = self.amount_total_in_currency_signed
        total_balance = self.amount_total_signed

        for account_id, account_amounts in amounts_by_account.items():
            account_currency = account_amounts["amount_currency"]
            account_balance = account_amounts["balance"]
            ratio = (
                abs(account_currency) / abs(total_currency)
                if total_currency
                else 1.0
            )

            if self.invoice_payment_term_id:
                is_draft = self.id != self._origin.id
                if is_draft:
                    tax_amount_currency = 0.0
                    tax_amount = 0.0
                    untaxed_amount_currency = 0.0
                    untaxed_amount = 0.0
                    sign = self.direction_sign
                    base_lines, _tax_lines = self._get_rounded_base_and_tax_lines(
                        round_from_tax_lines=False
                    )
                    AccountTax._add_accounting_data_in_base_lines_tax_details(
                        base_lines,
                        self.company_id,
                        include_caba_tags=self.always_tax_exigible,
                    )
                    tax_results = AccountTax._prepare_tax_lines(base_lines, self.company_id)
                    for _base_line, to_update in tax_results["base_lines_to_update"]:
                        untaxed_amount_currency += sign * to_update["amount_currency"]
                        untaxed_amount += sign * to_update["balance"]
                    for tax_line_vals in tax_results["tax_lines_to_add"]:
                        tax_amount_currency += sign * tax_line_vals["amount_currency"]
                        tax_amount += sign * tax_line_vals["balance"]
                else:
                    tax_amount_currency = self.amount_tax * sign
                    tax_amount = self.amount_tax_signed
                    untaxed_amount_currency = self.amount_untaxed * sign
                    untaxed_amount = self.amount_untaxed_signed

                invoice_payment_terms = self.invoice_payment_term_id._compute_terms(
                    date_ref=self.invoice_date or self.date or fields.Date.context_today(self),
                    currency=self.currency_id,
                    tax_amount_currency=tax_amount_currency * ratio,
                    tax_amount=tax_amount * ratio,
                    untaxed_amount_currency=untaxed_amount_currency * ratio,
                    untaxed_amount=untaxed_amount * ratio,
                    company=self.company_id,
                    cash_rounding=self.invoice_cash_rounding_id,
                    sign=sign,
                )
                for term_line in invoice_payment_terms["line_ids"]:
                    key = frozendict({
                        "move_id": self.id,
                        "date_maturity": fields.Date.to_date(term_line.get("date")),
                        "discount_date": invoice_payment_terms.get("discount_date"),
                        "account_receivable_split_id": account_id,
                    })
                    values = {
                        "balance": term_line["company_amount"],
                        "amount_currency": term_line["foreign_amount"],
                        "discount_date": invoice_payment_terms.get("discount_date"),
                        "discount_balance": invoice_payment_terms.get("discount_balance") or 0.0,
                        "discount_amount_currency": invoice_payment_terms.get("discount_amount_currency") or 0.0,
                    }
                    if key not in needed_terms:
                        needed_terms[key] = values
                    else:
                        needed_terms[key]["balance"] += values["balance"]
                        needed_terms[key]["amount_currency"] += values["amount_currency"]
            else:
                key = frozendict({
                    "move_id": self.id,
                    "date_maturity": fields.Date.to_date(self.invoice_date_due),
                    "discount_date": False,
                    "account_receivable_split_id": account_id,
                })
                needed_terms[key] = {
                    "balance": account_balance,
                    "amount_currency": account_currency,
                    "discount_balance": 0.0,
                    "discount_amount_currency": 0.0,
                }
        return needed_terms

    @api.depends(
        "invoice_payment_term_id",
        "invoice_date",
        "currency_id",
        "amount_total_in_currency_signed",
        "invoice_date_due",
        "invoice_line_ids",
        "invoice_line_ids.product_id",
        "invoice_line_ids.price_subtotal",
        "partner_id",
        "fiscal_position_id",
    )
    def _compute_needed_terms(self):
        super()._compute_needed_terms()
        for invoice in self.filtered(lambda move: move.is_sale_document(include_receipts=True)):
            if not invoice._should_split_account_receivable_by_product():
                continue
            invoice.needed_terms = invoice._build_product_account_receivable_needed_terms()
            invoice.needed_terms_dirty = True

    def _get_product_account_receivable_summary_for_report(self):
        self.ensure_one()
        amounts = self._get_account_receivable_amounts_by_product()
        account_model = self.env["account.account"]
        summary = []
        for account_id, values in amounts.items():
            account = account_model.browse(account_id)
            summary.append({
                "account": account,
                "account_code": account.code,
                "account_name": account.name,
                "amount": values["amount_currency"],
                "amount_formatted": self.currency_id.format(values["amount_currency"]),
            })
        return summary
