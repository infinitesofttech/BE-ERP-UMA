import requests
import json
import time
from datetime import date

BASE_URL = "https://umaERP.pythonanywhere.com/api"
RUN_ID = str(int(time.time()))
today_str = date.today().isoformat()

session = requests.Session()
session.headers.update({
    'Content-Type': 'application/json',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
})

def log(msg):
    try:
        print(msg, flush=True)
    except Exception:
        print(msg.encode('ascii', 'replace').decode('ascii'), flush=True)

def login():
    res = session.post(f"{BASE_URL}/auth/login/", json={
        "username": "rajesh.admin",
        "password": "admin123"
    }, timeout=15)
    if res.status_code != 200:
        raise Exception(f"Login failed: {res.status_code} - {res.text}")
    data = res.json()
    token = data.get('access') or data.get('tokens', {}).get('access') or data.get('token')
    session.headers.update({'Authorization': f"Bearer {token}"})
    log("[OK] Authenticated as Admin on PythonAnywhere via JWT Token.")

def test_full_lifecycle():
    log("\n" + "=" * 80)
    log("TESTING LIVE PYTHONANYWHERE BACKEND CRUD & APPROVAL LIFECYCLE")
    log("=" * 80)

    # 1. LEAD
    log("\n[1/18] LEAD: Testing Create, Read, Update...")
    lead_no = f"LEAD-PA-{RUN_ID}"
    lead_payload = {
        'leadNo': lead_no,
        'companyName': f'Gujarat Chemical Corp {RUN_ID}',
        'contactPerson': 'Bhavesh Mehta',
        'mobile': '9876543210',
        'email': f'bhavesh_{RUN_ID}@gujaratchem.com',
        'productName': 'Distillation Column 5000L SS316',
        'status': 'new',
        'priority': 'high',
        'createdDate': today_str,
    }
    r = session.post(f"{BASE_URL}/leads/", json=lead_payload, timeout=15)
    assert r.status_code in [200, 201], f"Lead Create failed: {r.status_code} {r.text}"
    lead_id = r.json().get('id') or lead_no
    log(f"  -> Created Lead: {lead_id} (Status: {r.json().get('status')})")

    # Update Lead
    r_up = session.patch(f"{BASE_URL}/leads/{lead_id}/", json={"status": "qualified", "budget": 7500000}, timeout=15)
    assert r_up.status_code == 200, f"Lead Update failed: {r_up.status_code} {r_up.text}"
    log(f"  -> Updated Lead {lead_id} to 'qualified'")

    # 2. ENQUIRY & CUSTOMER
    log("\n[2/18] ENQUIRY: Testing Customer & Enquiry creation...")
    cust_id = f"CUST-PA-{RUN_ID}"
    cust_payload = {
        'id': cust_id,
        'customerCode': cust_id,
        'companyName': lead_payload['companyName'],
        'contactPerson': lead_payload['contactPerson'],
        'mobile': lead_payload['mobile'],
        'email': lead_payload['email'],
        'city': 'Ahmedabad',
    }
    r_cust = session.post(f"{BASE_URL}/customers/", json=cust_payload, timeout=15)
    assert r_cust.status_code in [200, 201], f"Customer create failed: {r_cust.status_code} {r_cust.text}"
    log(f"  -> Created Customer: {cust_id}")

    enq_no = f"ENQ-PA-{RUN_ID}"
    enq_payload = {
        'enquiryNo': enq_no,
        'leadId': lead_id,
        'customerId': cust_id,
        'customerName': lead_payload['companyName'],
        'enquiryDate': today_str,
        'requirement': 'Design and manufacturing of 5000L SS316 Distillation Column',
        'machineProduct': lead_payload['productName'],
        'quantity': 1,
        'status': 'under_review',
    }
    r_enq = session.post(f"{BASE_URL}/enquiries/", json=enq_payload, timeout=15)
    assert r_enq.status_code in [200, 201], f"Enquiry create failed: {r_enq.status_code} {r_enq.text}"
    enq_id = r_enq.json().get('id') or enq_no
    
    r_enq_up = session.patch(f"{BASE_URL}/enquiries/{enq_id}/", json={'status': 'quotation_ready'}, timeout=15)
    assert r_enq_up.status_code == 200, f"Enquiry update failed: {r_enq_up.status_code} {r_enq_up.text}"
    log(f"  -> Created & Updated Enquiry: {enq_id} to 'quotation_ready'")

    # 3. QUOTATION
    log("\n[3/18] QUOTATION: Testing Quotation Creation & Approval...")
    quo_no = f"QT-PA-{RUN_ID}"
    quo_payload = {
        'quotationNumber': quo_no,
        'currentRevision': 'Rev-00',
        'date': today_str,
        'validUntil': '2026-12-31',
        'customerId': cust_id,
        'customerName': lead_payload['companyName'],
        'contactPerson': lead_payload['contactPerson'],
        'contactEmail': lead_payload['email'],
        'enquiryId': enq_id,
        'revisions': [{
            'revisionNumber': 'Rev-00',
            'status': 'draft',
            'grandTotal': 7200000,
            'machineProduct': lead_payload['productName'],
            'items': [{'itemNo': 1, 'description': lead_payload['productName'], 'qty': 1, 'unitRate': 7200000, 'amount': 7200000}]
        }],
    }
    r_quo = session.post(f"{BASE_URL}/quotations/", json=quo_payload, timeout=15)
    assert r_quo.status_code in [200, 201], f"Quotation create failed: {r_quo.status_code} {r_quo.text}"
    quo_id = r_quo.json().get('id') or quo_no

    # Approve Quotation
    r_quo_app = session.post(f"{BASE_URL}/quotations/{quo_id}/update-status/", json={'revisionNumber': 'Rev-00', 'status': 'approved'}, timeout=15)
    assert r_quo_app.status_code == 200, f"Quotation approval failed: {r_quo_app.status_code} {r_quo_app.text}"
    log(f"  -> Quotation {quo_id} Created and Approved!")

    # 4. CUSTOMER PO
    log("\n[4/18] CUSTOMER PO: Testing Customer PO Receipt and Acceptance...")
    po_no = f"CPO-PA-{RUN_ID}"
    cpo_payload = {
        'poNumber': po_no,
        'customerId': cust_id,
        'customerName': lead_payload['companyName'],
        'quotationId': quo_id,
        'quotationNumber': quo_no,
        'poDate': today_str,
        'deliveryDate': '2026-11-30',
        'poAmount': 7200000.0,
        'status': 'received',
    }
    r_cpo = session.post(f"{BASE_URL}/customer-pos/", json=cpo_payload, timeout=15)
    assert r_cpo.status_code in [200, 201], f"Customer PO create failed: {r_cpo.status_code} {r_cpo.text}"
    cpo_id = r_cpo.json().get('id') or po_no
    
    r_cpo_up = session.patch(f"{BASE_URL}/customer-pos/{cpo_id}/", json={'status': 'accepted'}, timeout=15)
    assert r_cpo_up.status_code == 200, f"Customer PO accept failed: {r_cpo_up.status_code} {r_cpo_up.text}"
    log(f"  -> Customer PO {cpo_id} Created and Accepted!")

    # 5. SALES ORDER
    log("\n[5/18] SALES ORDER: Testing Sales Order Creation and Confirmation...")
    so_no = f"SO-PA-{RUN_ID}"
    so_payload = {
        'salesOrderNumber': so_no,
        'customerPoId': cpo_id,
        'customerPoNumber': po_no,
        'quotationId': quo_id,
        'quotationNumber': quo_no,
        'customerId': cust_id,
        'customerName': lead_payload['companyName'],
        'orderDate': today_str,
        'targetDeliveryDate': '2026-11-30',
        'grandTotal': 7200000.0,
        'totalAmount': 7200000.0,
        'status': 'confirmed',
        'approvedBy': 'Bhavin Shah (Director)',
        'items': [{'itemNo': 1, 'productName': lead_payload['productName'], 'quantity': 1, 'unitRate': 7200000, 'totalAmount': 7200000}]
    }
    r_so = session.post(f"{BASE_URL}/sales-orders/", json=so_payload, timeout=15)
    assert r_so.status_code in [200, 201], f"Sales Order create failed: {r_so.status_code} {r_so.text}"
    so_id = r_so.json().get('id') or so_no
    log(f"  -> Sales Order {so_id} Created and Confirmed!")

    # 6. PROJECT / JOB
    log("\n[6/18] PROJECT / JOB: Testing Project & Job Master Creation...")
    prj_no = f"PRJ-PA-{RUN_ID}"
    job_no = f"JOB-PA-{RUN_ID}"
    prj_payload = {
        'id': prj_no,
        'projectNumber': prj_no,
        'jobNumber': job_no,
        'customerId': cust_id,
        'customerName': lead_payload['companyName'],
        'salesOrderId': so_id,
        'salesOrderNumber': so_no,
        'customerPoNumber': po_no,
        'productName': lead_payload['productName'],
        'orderValue': 7200000.0,
        'startDate': today_str,
        'targetDeliveryDate': '2026-11-30',
        'currentStatus': 'planning',
        'projectManagerName': 'Bhavin Shah',
    }
    r_prj = session.post(f"{BASE_URL}/projects/", json=prj_payload, timeout=15)
    assert r_prj.status_code in [200, 201], f"Project create failed: {r_prj.status_code} {r_prj.text}"
    prj_id = r_prj.json().get('id') or prj_no

    r_prj_up = session.patch(f"{BASE_URL}/projects/{prj_id}/", json={'currentStatus': 'in_progress', 'progressPercent': 15}, timeout=15)
    assert r_prj_up.status_code == 200, f"Project update failed: {r_prj_up.status_code} {r_prj_up.text}"
    log(f"  -> Project {prj_id} / Job {job_no} Created and Updated to 'in_progress'!")

    # 7. DESIGN JOB
    log("\n[7/18] DESIGN: Testing Design Job Approval & Release to Production...")
    des_no = f"DES-PA-{RUN_ID}"
    des_payload = {
        'designJobNumber': des_no,
        'projectId': prj_id,
        'projectNumber': prj_no,
        'jobNumber': job_no,
        'customerId': cust_id,
        'customerName': lead_payload['companyName'],
        'customerPoNumber': po_no,
        'salesOrderNumber': so_no,
        'productName': lead_payload['productName'],
        'targetCompletionDate': '2026-11-15',
        'status': 'under_review',
    }
    r_des = session.post(f"{BASE_URL}/designer/jobs/", json=des_payload, timeout=15)
    assert r_des.status_code in [200, 201], f"Design Job create failed: {r_des.status_code} {r_des.text}"
    des_id = r_des.json().get('id') or des_no

    # Approve & Release Design
    r_des_app = session.post(f"{BASE_URL}/designer/jobs/{des_id}/approve/", json={
        "approvedBy": "Dharmesh Joshi",
        "notes": "Approved for live production release"
    }, timeout=15)
    assert r_des_app.status_code == 200, f"Design Job approve failed: {r_des_app.status_code} {r_des_app.text}"

    r_des_rel = session.post(f"{BASE_URL}/designer/jobs/{des_id}/release-to-production/", timeout=15)
    assert r_des_rel.status_code == 200, f"Design release failed: {r_des_rel.status_code} {r_des_rel.text}"
    log(f"  -> Design Job {des_id} Approved and Released to Production!")

    # 8. BOM
    log("\n[8/18] BOM: Testing BOM Header & Items...")
    bom_no = f"BOM-PA-{RUN_ID}"
    bom_items = [
        {'itemNo': 1, 'itemCode': 'SS-PL-316L', 'itemName': 'SS 316L 32mm Shell Plate', 'quantity': 8, 'uom': 'Nos', 'estimatedRate': 350000, 'totalEstimatedAmount': 2800000},
        {'itemNo': 2, 'itemCode': 'FLG-WN-300', 'itemName': 'WNRF Flange 24-inch ANSI 300#', 'quantity': 6, 'uom': 'Nos', 'estimatedRate': 120000, 'totalEstimatedAmount': 720000},
        {'itemNo': 3, 'itemCode': 'GSK-SPW-316', 'itemName': 'Spiral Wound Gasket 24-inch', 'quantity': 12, 'uom': 'Nos', 'estimatedRate': 15000, 'totalEstimatedAmount': 180000},
    ]
    bom_payload = {
        'bomNumber': bom_no,
        'jobNumber': job_no,
        'designJobId': des_id,
        'preparedBy': 'Design Engineer (R&D)',
        'status': 'draft',
        'items': bom_items,
        'total_estimated_cost': 3700000.0,
    }
    r_bom = session.post(f"{BASE_URL}/designer/boms/", json=bom_payload, timeout=15)
    assert r_bom.status_code in [200, 201], f"BOM create failed: {r_bom.status_code} {r_bom.text}"
    bom_id = r_bom.json().get('id') or bom_no

    r_bom_app = session.patch(f"{BASE_URL}/designer/boms/{bom_id}/", json={'status': 'approved', 'approved_by': 'HOD Engineering'}, timeout=15)
    assert r_bom_app.status_code == 200, f"BOM approve failed: {r_bom_app.status_code} {r_bom_app.text}"
    log(f"  -> BOM {bom_id} Created and Approved with items!")

    # 9. MRP
    log("\n[9/18] MRP: Testing Material Requirements Planning...")
    mrp_id = f"MRP-PA-{RUN_ID}"
    mrp_payload = {
        'id': mrp_id,
        'project_id': prj_id,
        'job_id': job_no,
        'job_number': job_no,
        'customer_name': lead_payload['companyName'],
        'design_job_id': des_id,
        'bom_id': bom_id,
        'bom_number': bom_no,
        'status': 'PR Generated',
        'items': bom_items,
    }
    r_mrp = session.post(f"{BASE_URL}/material-requirements/", json=mrp_payload, timeout=15)
    assert r_mrp.status_code in [200, 201], f"MRP create failed: {r_mrp.status_code} {r_mrp.text}"
    log(f"  -> MRP {mrp_id} Created!")

    # 10. PURCHASE (PR & PO)
    log("\n[10/18] PURCHASE: Testing Purchase Requisition & Purchase Order...")
    pr_no = f"PR-PA-{RUN_ID}"
    pr_payload = {
        'prNumber': pr_no,
        'projectId': prj_id,
        'jobCode': job_no,
        'requestedBy': 'Store Officer',
        'requestDate': today_str,
        'requiredByDate': '2026-10-31',
        'status': 'Submitted',
        'total_estimated_cost': 3700000.0,
        'items': bom_items,
    }
    r_pr = session.post(f"{BASE_URL}/purchase-requisitions/", json=pr_payload, timeout=15)
    assert r_pr.status_code in [200, 201], f"PR create failed: {r_pr.status_code} {r_pr.text}"
    pr_id = r_pr.json().get('id') or pr_no

    r_pr_app = session.patch(f"{BASE_URL}/purchase-requisitions/{pr_id}/", json={'status': 'Approved', 'approvedBy': 'Purchase Head'}, timeout=15)
    assert r_pr_app.status_code == 200, f"PR approve failed: {r_pr_app.status_code} {r_pr_app.text}"

    po_ord_no = f"PO-PA-{RUN_ID}"
    po_ord_payload = {
        'poNumber': po_ord_no,
        'supplierId': 'SUP-001',
        'supplierName': 'Jindal Stainless Steel Ltd',
        'date': today_str,
        'deliveryDate': '2026-10-25',
        'projectId': prj_id,
        'jobCode': job_no,
        'status': 'Draft',
        'grandTotal': 3700000.0,
        'items': bom_items,
    }
    r_po = session.post(f"{BASE_URL}/purchase-orders/", json=po_ord_payload, timeout=15)
    assert r_po.status_code in [200, 201], f"PO create failed: {r_po.status_code} {r_po.text}"
    po_order_id = r_po.json().get('id') or po_ord_no

    r_po_app = session.patch(f"{BASE_URL}/purchase-orders/{po_order_id}/", json={'status': 'Approved', 'approvedBy': 'Commercial Director'}, timeout=15)
    assert r_po_app.status_code == 200, f"PO approve failed: {r_po_app.status_code} {r_po_app.text}"
    log(f"  -> PR {pr_id} and PO {po_order_id} Created and Approved!")

    # 11. GRN
    log("\n[11/18] GRN: Testing Goods Receipt Note Inward...")
    grn_no = f"GRN-PA-{RUN_ID}"
    grn_payload = {
        'grnNumber': grn_no,
        'date': today_str,
        'poId': po_order_id,
        'poNumber': po_ord_no,
        'supplierId': 'SUP-001',
        'supplierName': 'Jindal Stainless Steel Ltd',
        'receivedBy': 'Hitesh Rawal (Store Incharge)',
        'warehouseId': 'wh-main',
        'status': 'Accepted',
        'items': [
            {'itemCode': 'SS-PL-316L', 'itemName': 'SS 316L 32mm Shell Plate', 'receivedQuantity': 8, 'acceptedQuantity': 8, 'uom': 'Nos', 'unitPrice': 350000},
            {'itemNo': 2, 'itemCode': 'FLG-WN-300', 'itemName': 'WNRF Flange 24-inch ANSI 300#', 'receivedQuantity': 6, 'acceptedQuantity': 6, 'uom': 'Nos', 'unitPrice': 120000},
        ]
    }
    r_grn = session.post(f"{BASE_URL}/grns/", json=grn_payload, timeout=15)
    assert r_grn.status_code in [200, 201], f"GRN create failed: {r_grn.status_code} {r_grn.text}"
    log(f"  -> GRN {grn_no} Material Inward recorded!")

    # 12. MATERIAL ISSUE
    log("\n[12/18] MATERIAL ISSUE: Testing Issue to Shop Floor...")
    iss_no = f"ISS-PA-{RUN_ID}"
    iss_payload = {
        'issueNumber': iss_no,
        'projectId': prj_id,
        'jobNumber': job_no,
        'issuedTo': 'Shell Rolling & Fitting Station',
        'issuedBy': 'Store Officer',
        'issueDate': today_str,
        'status': 'Fully Issued',
        'totalIssueValue': 2800000.0,
        'items': [
            {'itemCode': 'SS-PL-316L', 'itemName': 'SS 316L 32mm Shell Plate', 'issuedQuantity': 8, 'uom': 'Nos'}
        ]
    }
    r_iss = session.post(f"{BASE_URL}/material-issues/", json=iss_payload, timeout=15)
    assert r_iss.status_code in [200, 201], f"Material Issue failed: {r_iss.status_code} {r_iss.text}"
    log(f"  -> Material Issue Slip {iss_no} Issued to Production!")

    # 13. PRODUCTION
    log("\n[13/18] PRODUCTION: Testing Work Order & Production Entry...")
    wo_no = f"WO-PA-{RUN_ID}"
    wo_payload = {
        'workOrderNumber': wo_no,
        'jobId': job_no,
        'jobNumber': job_no,
        'projectId': prj_id,
        'customerName': lead_payload['companyName'],
        'productName': lead_payload['productName'],
        'productionQuantity': 1,
        'status': 'Draft',
    }
    r_wo = session.post(f"{BASE_URL}/work-orders/", json=wo_payload, timeout=15)
    assert r_wo.status_code in [200, 201], f"Work order failed: {r_wo.status_code} {r_wo.text}"
    wo_id = r_wo.json().get('id') or wo_no

    r_wo_rel = session.post(f"{BASE_URL}/work-orders/{wo_id}/release/", timeout=15)
    assert r_wo_rel.status_code == 200, f"Work order release failed: {r_wo_rel.status_code} {r_wo_rel.text}"

    pentry_no = f"PENTRY-PA-{RUN_ID}"
    pentry_payload = {
        'productionEntryNumber': pentry_no,
        'entryDate': today_str,
        'jobNumber': job_no,
        'workOrderNumber': wo_no,
        'operationName': 'Final Hydro Testing & Vessel Cleaning',
        'operatorName': 'Ramesh Parmar (Certified Welder)',
        'producedQuantity': 1,
        'goodQuantity': 1,
        'rejectedQuantity': 0,
    }
    r_pe = session.post(f"{BASE_URL}/production-entries/", json=pentry_payload, timeout=15)
    assert r_pe.status_code in [200, 201], f"Production Entry failed: {r_pe.status_code} {r_pe.text}"
    log(f"  -> Work Order {wo_id} & Production Entry {pentry_no} logged successfully!")

    # 14. QC INSPECTION
    log("\n[14/18] QC INSPECTION: Testing Quality Clearance...")
    fg_no = f"FG-PA-{RUN_ID}"
    fg_payload = {
        'finishedGoodsNumber': fg_no,
        'jobNumber': job_no,
        'workOrderNumber': wo_no,
        'productName': lead_payload['productName'],
        'quantity': 1,
        'serialNumber': f"SN-VESSEL-{RUN_ID}",
        'status': 'Ready for QC',
        'qcStatus': 'Pending Inspection',
    }
    r_fg = session.post(f"{BASE_URL}/finished-goods/", json=fg_payload, timeout=15)
    assert r_fg.status_code in [200, 201], f"Finished goods create failed: {r_fg.status_code} {r_fg.text}"
    fg_id = r_fg.json().get('id') or fg_no

    r_qc_pass = session.post(f"{BASE_URL}/finished-goods/{fg_id}/qc-pass/", timeout=15)
    assert r_qc_pass.status_code == 200, f"QC pass failed: {r_qc_pass.status_code} {r_qc_pass.text}"
    log(f"  -> FG {fg_no} QC Passed and Cleared for Packing!")

    # 15. PACKING & DISPATCH
    log("\n[15/18] PACKING & DISPATCH: Testing Dispatch Order...")
    disp_no = f"DISP-PA-{RUN_ID}"
    disp_payload = {
        'dispatchNumber': disp_no,
        'jobNumber': job_no,
        'workOrderNumber': wo_no,
        'finishedGoodsNumber': fg_no,
        'customerId': cust_id,
        'customerName': lead_payload['companyName'],
        'productName': lead_payload['productName'],
        'quantity': 1,
        'packagingType': 'Wooden Saddle & Shrink Wrapped Tarpaulin',
        'transporterName': 'CJ Darcl Logistics Heavy ODC',
        'vehicleNumber': 'GJ-06-ZZ-1234',
        'driverName': 'Sukhdev Singh',
        'status': 'Ready for Dispatch',
    }
    r_disp = session.post(f"{BASE_URL}/dispatch-orders/", json=disp_payload, timeout=15)
    assert r_disp.status_code in [200, 201], f"Dispatch order create failed: {r_disp.status_code} {r_disp.text}"
    disp_id = r_disp.json().get('id') or disp_no

    r_disp_mark = session.post(f"{BASE_URL}/dispatch-orders/{disp_id}/mark-dispatched/", timeout=15)
    assert r_disp_mark.status_code == 200, f"Mark dispatched failed: {r_disp_mark.status_code} {r_disp_mark.text}"
    log(f"  -> Dispatch Order {disp_no} Dispatched (Vehicle: GJ-06-ZZ-1234)!")

    # 16. SALES INVOICE
    log("\n[16/18] SALES INVOICE: Testing Tax Invoice Generation...")
    inv_no = f"INV-PA-{RUN_ID}"
    inv_payload = {
        'invoiceNumber': inv_no,
        'invoiceDate': today_str,
        'dueDate': '2026-11-30',
        'customerId': cust_id,
        'customerName': lead_payload['companyName'],
        'salesOrderId': so_id,
        'salesOrderNumber': so_no,
        'jobNumber': job_no,
        'grandTotal': 7200000.0,
        'taxableAmount': 6101694.92,
        'status': 'Draft',
        'paymentStatus': 'Unpaid',
        'items': [{'itemNo': 1, 'description': lead_payload['productName'], 'amount': 7200000.0}]
    }
    r_inv = session.post(f"{BASE_URL}/sales-invoices/", json=inv_payload, timeout=15)
    assert r_inv.status_code in [200, 201], f"Invoice create failed: {r_inv.status_code} {r_inv.text}"
    inv_id = r_inv.json().get('id') or inv_no

    r_inv_app = session.patch(f"{BASE_URL}/sales-invoices/{inv_id}/", json={'status': 'Approved'}, timeout=15)
    assert r_inv_app.status_code == 200, f"Invoice approve failed: {r_inv_app.status_code} {r_inv_app.text}"
    log(f"  -> Sales Invoice {inv_no} Created and Approved (Rs.72,00,000)!")

    # 17. PAYMENT
    log("\n[17/18] PAYMENT: Testing Payment Settlement...")
    r_pay = session.post(f"{BASE_URL}/sales-invoices/{inv_id}/record-payment/", json={
        'amount': 7200000.0,
        'paymentMode': 'NEFT/RTGS',
        'referenceNumber': f'UTR-SBI-{RUN_ID}',
    }, timeout=15)
    assert r_pay.status_code == 200, f"Record payment failed: {r_pay.status_code} {r_pay.text}"
    log(f"  -> Payment Recorded for Invoice {inv_no}! Status: Paid")

    # 18. INSTALLATION
    log("\n[18/18] INSTALLATION: Testing Customer Machine Commissioning...")
    cm_no = f"MACH-PA-{RUN_ID}"
    cm_payload = {
        'customerMachineId': cm_no,
        'customerId': cust_id,
        'customerName': lead_payload['companyName'],
        'jobNumber': job_no,
        'salesOrderId': so_id,
        'dispatchNumber': disp_no,
        'machineName': lead_payload['productName'],
        'serialNumber': f"SN-VESSEL-{RUN_ID}",
        'installationDate': today_str,
        'commissioningDate': today_str,
        'status': 'Installed & Commissioned',
    }
    r_cm = session.post(f"{BASE_URL}/customer-machines/", json=cm_payload, timeout=15)
    assert r_cm.status_code in [200, 201], f"Customer machine failed: {r_cm.status_code} {r_cm.text}"
    log(f"  -> Asset {cm_no} Commissioned & Active on site!")

    log("\n" + "=" * 80)
    log("[SUCCESS] ALL 18+ LIFECYCLE STAGES SUCCESSFULLY VERIFIED ON LIVE PYTHONANYWHERE!")
    log("=" * 80)

if __name__ == '__main__':
    login()
    test_full_lifecycle()
