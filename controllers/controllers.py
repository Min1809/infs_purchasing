# -*- coding: utf-8 -*-
# from odoo import http


# class InfsPurchasing(http.Controller):
#     @http.route('/infs_purchasing/infs_purchasing', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/infs_purchasing/infs_purchasing/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('infs_purchasing.listing', {
#             'root': '/infs_purchasing/infs_purchasing',
#             'objects': http.request.env['infs_purchasing.infs_purchasing'].search([]),
#         })

#     @http.route('/infs_purchasing/infs_purchasing/objects/<model("infs_purchasing.infs_purchasing"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('infs_purchasing.object', {
#             'object': obj
#         })

