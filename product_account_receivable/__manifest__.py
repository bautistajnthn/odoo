# -*- coding: utf-8 -*-
{
    "name": "Product Account Receivable",
    "summary": "Set account receivable per product or category; invoice journal items and payments post to those AR accounts.",
    "version": "19.0.1.1.0",
    "category": "Accounting/Accounting",
    "author": "bautistajnthn",
    "license": "LGPL-3",
    "price": 40.00,
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
