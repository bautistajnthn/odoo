# -*- coding: utf-8 -*-

from collections import defaultdict

from odoo import Command, models


class AccountPayment(models.Model):
    _inherit = "account.payment"

    def _get_invoices_for_product_ar_split(self):
        """Return invoices whose receivable residuals should drive payment AR splits."""
        self.ensure_one()
        invoices = self.invoice_ids | self.reconciled_invoice_ids
        if "paid_invoice_ids" in self._fields and self.paid_invoice_ids:
            invoices |= self.paid_invoice_ids
        if invoices:
            return invoices.filtered(
                lambda move: move.is_sale_document(include_receipts=True)
                and move.state == "posted"
            )

        # Payment register sets destination to a specific invoice AR account.
        # Do not rediscover open invoices (would wrongly reallocate across accounts).
        partner_ar = self.partner_id.with_company(
            self.company_id
        ).property_account_receivable_id
        is_collection = bool(getattr(self, "is_collection_payment", False))
        if (
            not is_collection
            and partner_ar
            and self.destination_account_id
            and self.destination_account_id != partner_ar
        ):
            return self.env["account.move"]

        if not self.partner_id:
            return self.env["account.move"]

        return self.env["account.move"].search(
            [
                ("partner_id", "=", self.partner_id.id),
                ("company_id", "=", self.company_id.id),
                ("move_type", "=", "out_invoice"),
                ("state", "=", "posted"),
                ("payment_state", "in", ("not_paid", "partial")),
                ("amount_residual", ">", 0),
            ],
            order="invoice_date_due asc, invoice_date asc, id asc",
        )

    def _get_receivable_residuals_for_product_ar_split(self):
        """FIFO receivable lines: list of (account, residual_currency, residual_balance)."""
        self.ensure_one()
        invoices = self._get_invoices_for_product_ar_split()
        if not invoices:
            return []

        residuals = []
        for invoice in invoices.sorted(
            key=lambda move: (
                move.invoice_date_due or move.invoice_date or move.date,
                move.id,
            )
        ):
            receivable_lines = invoice.line_ids.filtered(
                lambda line: line.account_id.account_type == "asset_receivable"
                and not line.reconciled
                and line.amount_residual
            ).sorted(key=lambda line: (line.date_maturity or invoice.invoice_date_due or line.date, line.id))
            for line in receivable_lines:
                residual_currency = abs(line.amount_residual_currency)
                residual_balance = abs(line.amount_residual)
                if not residual_currency and not residual_balance:
                    continue
                residuals.append((line.account_id, residual_currency, residual_balance))
        return residuals

    def _get_payment_ar_amounts_by_account(self, amount_currency, balance):
        """Allocate payment counterpart amounts across product AR accounts (FIFO).

        Returns ordered list of (account_id, amount_currency, balance) using the same
        signs as a standard payment counterpart line. Remaining amount (overpayment /
        change) stays on ``destination_account_id``.
        """
        self.ensure_one()
        residuals = self._get_receivable_residuals_for_product_ar_split()
        if not residuals:
            return []

        sign_currency = 1 if amount_currency >= 0 else -1
        sign_balance = 1 if balance >= 0 else -1
        remaining_currency = abs(amount_currency)
        remaining_balance = abs(balance)
        if not remaining_currency and not remaining_balance:
            return []

        currency = self.currency_id
        company_currency = self.company_id.currency_id
        allocated = defaultdict(lambda: {"amount_currency": 0.0, "balance": 0.0})
        account_order = []

        for account, residual_currency, residual_balance in residuals:
            if currency.is_zero(remaining_currency) and company_currency.is_zero(remaining_balance):
                break
            apply_currency = min(remaining_currency, residual_currency)
            if residual_currency:
                ratio = apply_currency / residual_currency
                apply_balance = company_currency.round(residual_balance * ratio)
            else:
                apply_balance = min(remaining_balance, residual_balance)
                apply_currency = 0.0

            apply_currency = currency.round(apply_currency)
            apply_balance = company_currency.round(apply_balance)
            if currency.is_zero(apply_currency) and company_currency.is_zero(apply_balance):
                continue

            if account.id not in allocated:
                account_order.append(account.id)
            allocated[account.id]["amount_currency"] += apply_currency
            allocated[account.id]["balance"] += apply_balance
            remaining_currency = currency.round(remaining_currency - apply_currency)
            remaining_balance = company_currency.round(remaining_balance - apply_balance)

        if not currency.is_zero(remaining_currency) or not company_currency.is_zero(remaining_balance):
            fallback = self.destination_account_id
            if fallback:
                if fallback.id not in allocated:
                    account_order.append(fallback.id)
                allocated[fallback.id]["amount_currency"] += remaining_currency
                allocated[fallback.id]["balance"] += remaining_balance

        # Fix rounding drift on the last account so totals match the counterpart exactly.
        total_currency = sum(values["amount_currency"] for values in allocated.values())
        total_balance = sum(values["balance"] for values in allocated.values())
        currency_diff = currency.round(abs(amount_currency) - total_currency)
        balance_diff = company_currency.round(abs(balance) - total_balance)
        if account_order and (currency_diff or balance_diff):
            allocated[account_order[-1]]["amount_currency"] = currency.round(
                allocated[account_order[-1]]["amount_currency"] + currency_diff
            )
            allocated[account_order[-1]]["balance"] = company_currency.round(
                allocated[account_order[-1]]["balance"] + balance_diff
            )

        return [
            (
                account_id,
                sign_currency * allocated[account_id]["amount_currency"],
                sign_balance * allocated[account_id]["balance"],
            )
            for account_id in account_order
            if not currency.is_zero(allocated[account_id]["amount_currency"])
            or not company_currency.is_zero(allocated[account_id]["balance"])
        ]

    def _should_split_payment_ar_by_product(self, amount_currency=None, balance=None):
        self.ensure_one()
        if self.partner_type != "customer" or self.payment_type != "inbound":
            return False
        if amount_currency is None or balance is None:
            # Approximate signs for inbound: counterpart is credit (negative).
            amount_currency = -self.amount
            balance = -self.currency_id._convert(
                self.amount,
                self.company_id.currency_id,
                self.company_id,
                self.date,
            )
        amounts = self._get_payment_ar_amounts_by_account(amount_currency, balance)
        if len(amounts) > 1:
            return True
        if len(amounts) == 1:
            account_id = amounts[0][0]
            return bool(
                self.destination_account_id
                and self.destination_account_id.id != account_id
            )
        return False

    def _prepare_move_line_default_vals(self, write_off_line_vals=None, force_balance=None):
        line_vals_list = super()._prepare_move_line_default_vals(
            write_off_line_vals=write_off_line_vals,
            force_balance=force_balance,
        )
        self.ensure_one()
        if len(line_vals_list) < 2:
            return line_vals_list

        liquidity_vals = line_vals_list[0]
        counterpart_vals = line_vals_list[1]
        writeoff_vals = line_vals_list[2:]

        splits = self._get_payment_ar_amounts_by_account(
            counterpart_vals.get("amount_currency", 0.0),
            counterpart_vals.get("debit", 0.0) - counterpart_vals.get("credit", 0.0),
        )
        if len(splits) <= 1 and not (
            len(splits) == 1 and splits[0][0] != counterpart_vals.get("account_id")
        ):
            return line_vals_list

        if not splits:
            return line_vals_list

        currency = self.currency_id
        company_currency = self.company_id.currency_id
        counterpart_lines = []
        for account_id, amount_currency, balance in splits:
            # Fully allocated to product ARs: do not keep a zero partner AR line.
            if currency.is_zero(amount_currency) and company_currency.is_zero(balance):
                continue
            line = dict(counterpart_vals)
            line["account_id"] = account_id
            line["amount_currency"] = amount_currency
            line["debit"] = balance if balance > 0.0 else 0.0
            line["credit"] = -balance if balance < 0.0 else 0.0
            counterpart_lines.append(line)
        if not counterpart_lines:
            return line_vals_list
        return [liquidity_vals] + counterpart_lines + writeoff_vals

    def _synchronize_to_moves(self, changed_fields):
        """Support multiple AR counterpart lines when splitting by product account."""
        if not any(
            field_name in changed_fields
            for field_name in self._get_trigger_fields_to_synchronize()
        ):
            return

        multi_payments = self.env["account.payment"]
        for pay in self:
            if not pay.move_id or pay.move_id.state == "posted":
                continue
            liquidity_lines, counterpart_lines, writeoff_lines = pay._seek_for_lines()
            write_off_line_vals = []
            if liquidity_lines and counterpart_lines and writeoff_lines:
                write_off_line_vals.append({
                    "name": writeoff_lines[0].name,
                    "account_id": writeoff_lines[0].account_id.id,
                    "partner_id": writeoff_lines[0].partner_id.id,
                    "currency_id": writeoff_lines[0].currency_id.id,
                    "amount_currency": sum(writeoff_lines.mapped("amount_currency")),
                    "balance": sum(writeoff_lines.mapped("balance")),
                })
            line_vals_list = pay._prepare_move_line_default_vals(
                write_off_line_vals=write_off_line_vals
            )
            if (
                len(counterpart_lines) > 1
                or len(line_vals_list) > 2 + len(write_off_line_vals)
                or pay._should_split_payment_ar_by_product()
            ):
                multi_payments |= pay
                line_ids_commands = [
                    Command.update(liquidity_lines.id, line_vals_list[0])
                    if liquidity_lines
                    else Command.create(line_vals_list[0]),
                ]
                for line in counterpart_lines + writeoff_lines:
                    line_ids_commands.append(Command.delete(line.id))
                for extra_line_vals in line_vals_list[1:]:
                    line_ids_commands.append(Command.create(extra_line_vals))

                to_write = {
                    "date": pay.date,
                    "partner_id": pay.partner_id.id,
                    "currency_id": pay.currency_id.id,
                    "partner_bank_id": pay.partner_bank_id.id,
                    "line_ids": line_ids_commands,
                }
                if "journal_id" in changed_fields:
                    to_write.update({
                        "name": "/",
                        "journal_id": pay.journal_id.id,
                    })
                pay.move_id.with_context(skip_invoice_sync=True).write(to_write)
                pay._remove_zero_amount_receivable_lines()

        remaining = self - multi_payments
        if remaining:
            super(AccountPayment, remaining)._synchronize_to_moves(changed_fields)

    def _remove_zero_amount_receivable_lines(self):
        """Drop AR counterpart lines with no amount (e.g. unused partner AR)."""
        for pay in self:
            move = pay.move_id
            if not move or move.state == "posted":
                continue
            currency = pay.currency_id
            company_currency = pay.company_id.currency_id
            zero_lines = move.line_ids.filtered(
                lambda line: line.account_id.account_type == "asset_receivable"
                and currency.is_zero(line.amount_currency)
                and company_currency.is_zero(line.balance)
            )
            if zero_lines:
                move.with_context(skip_invoice_sync=True).write({
                    "line_ids": [Command.delete(line.id) for line in zero_lines],
                })

    def _generate_journal_entry(self, write_off_line_vals=None, force_balance=None, line_ids=None):
        res = super()._generate_journal_entry(
            write_off_line_vals=write_off_line_vals,
            force_balance=force_balance,
            line_ids=line_ids,
        )
        self._remove_zero_amount_receivable_lines()
        return res
