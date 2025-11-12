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
    'depends': ['purchase'],
    'data': [
        "security/group.xml",
        "views/purchaseorder.xml",
        "views/purchaseorderline.xml",
        "views/purchaseorder_compare_product.xml",
        "views/emails.xml",
        ],
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
    'application': True,
    'sequence': -100,
}