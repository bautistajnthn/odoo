# -*- coding: utf-8 -*-
{
    "name": "Account Payable – Split AP by Product",
    "summary": "Per-product / category account payable (AP). Split vendor bill journal items and vendor payments by product AP instead of one partner payable.",
    "version": "19.0.1.0.0",
    "category": "Accounting/Accounting",
    "author": "bautistajnthn",
    "license": "LGPL-3",
    "price": 5.00,
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
