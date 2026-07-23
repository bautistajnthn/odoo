# -*- coding: utf-8 -*-
{
    "name": "Product Account Receivable",
    "summary": "Assign receivable accounts per product or category and split customer invoice and payment journal entries accordingly.",
    "version": "19.0.1.1.0",
    "category": "Accounting/Accounting",
    "author": "Jonathan Bautista",
    "license": "LGPL-3",
    "price": 49.00,
    "currency": "EUR",
    "depends": [
        "account",
        "awb_reports",
    ],
    "data": [
        "views/product_views.xml",
        "report/report_invoice.xml",
        "report/report_soa_invoice.xml",
    ],
    "installable": True,
    "application": False,
    "description": """
Product Account Receivable
==========================

Odoo uses one customer receivable account by default. This module lets you define
**account receivable per product or product category**, then posts customer invoices
and inbound payments across the correct receivable accounts automatically.

Ideal for businesses that track receivables by product line, project type, revenue
stream, or cost center.

Key Features
------------

* **Product & category receivable accounts**
  Set a company-dependent Account Receivable on product templates and categories.
  Resolution order: product → category → customer → company default.
  Fiscal positions are applied when mapping accounts.

* **Invoice journal entry split**
  Customer invoices with mixed receivable accounts create separate payment-term /
  receivable lines per account, so the balance sheet reflects the right AR accounts.

* **Payment allocation (FIFO)**
  Customer payments allocate counterpart amounts across open product receivable
  residuals. Overpayments remain on the standard destination account.

* **Invoice report clarity**
  Customer invoice PDF/HTML shows the receivable account per product line and an
  Account Receivable Summary when more than one account is used.

* **Multi-company ready**
  Receivable properties are company-dependent and respect the invoice company context.

Who Is This For?
----------------

* Companies that need receivable sub-ledgers by product or service type
* Organizations reporting AR separately for different business lines
* Accounting teams that currently fix receivable postings with manual journal entries

How It Works
------------

1. Configure Account Receivable on the product category and/or product.
2. Create a customer invoice with those products.
3. Confirm the invoice — receivable lines are split when needed.
4. Register a customer payment — payment counterparts follow open AR residuals.
5. Review the invoice report for line-level and summary receivable information.

Technical Notes
---------------

* Depends on the standard Invoicing / Accounting app (``account``).
* Compatible with Odoo 19.
* Does not replace partner receivable settings; it extends them at product level.

Support
-------

Developed by **Jonathan Bautista**.
For questions, bugs, or customization requests, contact the author via the Apps Store
publisher profile.
""",
}
