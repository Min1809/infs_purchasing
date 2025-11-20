/** @odoo-module **/

import { ListRenderer } from "@web/views/list/list_renderer";
import { patch } from "@web/core/utils/patch";

patch(ListRenderer.prototype, {
    /**
     * Add visual separators between different products in purchase order line comparison
     */
    async onWillUpdateProps(nextProps) {
        await super.onWillUpdateProps(...arguments);
        
        if (this.props.list?.jsClass === "purchase_order_line_compare") {
            this._addProductGroupAttributes();
        }
    },

    async onMounted() {
        await super.onMounted(...arguments);
        
        if (this.props.list?.jsClass === "purchase_order_line_compare") {
            this._addProductGroupAttributes();
        }
    },

    _addProductGroupAttributes() {
        // Wait for the next tick to ensure DOM is ready
        setTimeout(() => {
            const rows = this.rootRef?.el?.querySelectorAll("tbody tr.o_data_row");
            if (!rows || rows.length === 0) return;

            let lastProductId = null;
            let productGroupIndex = 0;

            rows.forEach((row, index) => {
                // Get the product_id from the row data
                const recordId = row.dataset.id;
                if (!recordId) return;

                // Find the record from the list
                const record = this.props.list.records.find(r => r.id == recordId);
                if (!record) return;

                const currentProductId = record.data.product_id?.[0];
                const hasQty = record.data.product_qty > 0;

                // Mark if product changed from previous row
                if (index > 0 && currentProductId !== lastProductId) {
                    row.setAttribute("data-product-changed", "true");
                    productGroupIndex++;
                } else {
                    row.setAttribute("data-product-changed", "false");
                }

                // Add group index for alternating colors
                row.setAttribute("data-product-group", productGroupIndex % 2 === 0 ? "even" : "odd");
                
                // Mark rows with quantity
                row.setAttribute("data-has-qty", hasQty ? "true" : "false");

                lastProductId = currentProductId;
            });
        }, 100);
    },
});
