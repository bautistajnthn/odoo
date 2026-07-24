# -*- coding: utf-8 -*-
{
    "name": "Account Receivable – Split AR by Product",
    "summary": "Per-product / category account receivable (AR). Split invoice journal items and customer payments by product AR instead of one partner receivable.",
    "version": "19.0.1.1.0",
    "category": "Accounting/Accounting",
    "author": "bautistajnthn",
    "license": "LGPL-3",
    "price": 19.00,
    "currency": "EUR",
    "depends": [
        "account",
    ],
    "data": [
        "views/product_views.xml",
        "report/report_invoice.xml",
    ],
    "images": [
        "static/description/main_screenshot.png",
    ],
    "installable": True,
    "application": False,
}
