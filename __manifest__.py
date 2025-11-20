{
    'name': 'INFS Purchasing',
    'version': '17.0.1.0.0',
    'summary': 'Purchasing Module customization and configuration',
    'description': """
        Features : 
        - yes.
    """,
    'category': 'Purchases',
    'author': 'INFS',
    'depends': ['base','crm','purchase','purchase_requisition','infs_crm'],
    'data': [
        # "data/sequence.xml",
        "security/group.xml",
        "security/ir.model.access.csv",
        # "views/purchaseorder.xml",
        # "views/purchaseorderline.xml",
        # "views/purchaseordergroup.xml",
        # "wizard/purchase_group_cancel_wizard_view.xml",
        # "views/purchaseorder_compare_product.xml",
        # "views/emails.xml",
        ],
    'assets': {
        'web.assets_backend': [
            'infs_purchasing/static/src/css/purchase_comparison.css',
            'infs_purchasing/static/src/js/purchase_order_line_compare.js',
        ],
    },
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
    'application': True,
    'sequence': -100,
}