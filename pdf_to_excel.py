import os
import re
import warnings
import pdfplumber
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from datetime import datetime

# Suppress font descriptor warnings from reportlab
warnings.filterwarnings("ignore", message="Could not get FontBBox")

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")

SANTOSH_GSTIN = "27AVDPB1482D1Z2"
MARUTI_GSTIN = "27IYXPD8592R1ZS"


def extract_data(pdf_path):
    with pdfplumber.open(pdf_path) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)

    # LR No
    lr_match = re.search(r'Lr No\.\s*\n?\s*(\d{8,})', text)
    lr_no = lr_match.group(1).strip() if lr_match else ""

    # Invoice No
    inv_match = re.search(r'Invoice No\.\s*\n?\s*(FOP[A-Z]\d+)', text)
    invoice_no = inv_match.group(1).strip() if inv_match else ""

    # Invoice Date
    date_match = re.search(r'Invoice Date\s*\n?\s*(\d{2}-\w{3}-\d{4})', text)
    invoice_date = date_match.group(1).strip() if date_match else ""

    # Month derived from invoice date
    month = ""
    if invoice_date:
        try:
            dt = datetime.strptime(invoice_date, "%d-%b-%Y")
            month = dt.strftime("%B")
        except Exception:
            pass

    # All GSTINs in document — first = Delhivery (From section), second = Bill To
    gstin_matches = re.findall(r'GSTIN\s*:\s*([A-Z0-9]+)', text)
    delhivery_gstin = gstin_matches[0] if gstin_matches else ""
    bill_to_gstin = gstin_matches[1] if len(gstin_matches) > 1 else ""

    # Owner based on Bill To GSTIN
    if SANTOSH_GSTIN in bill_to_gstin:
        owner = "Santosh"
    elif MARUTI_GSTIN in bill_to_gstin:
        owner = "Maruti"
    else:
        owner = bill_to_gstin  # unknown, store raw GSTIN for review

    # Sub Total (Basic Amount)
    subtotal_match = re.search(r'Sub Total\s+([\d,]+\.?\d*)', text)
    basic_amount = float(subtotal_match.group(1).replace(",", "")) if subtotal_match else 0.0

    # CGST
    cgst_match = re.search(r'CGST\s+[\d.]+\s+([\d,]+\.?\d*)', text)
    cgst = float(cgst_match.group(1).replace(",", "")) if cgst_match else 0.0

    # SGST
    sgst_match = re.search(r'SGST\s+[\d.]+\s+([\d,]+\.?\d*)', text)
    sgst = float(sgst_match.group(1).replace(",", "")) if sgst_match else 0.0

    # IGST
    igst_match = re.search(r'IGST\s+[\d.]+\s+([\d,]+\.?\d*)', text)
    igst = float(igst_match.group(1).replace(",", "")) if igst_match else 0.0

    # Total (match "Total Rs.XXX" but not "Grand Total")
    total_match = re.search(r'(?<!Grand )Total\s+Rs\.([\d,]+\.?\d*)', text)
    total = float(total_match.group(1).replace(",", "")) if total_match else 0.0

    return {
        "lr_no": lr_no,
        "month": month,
        "date": invoice_date,
        "gstin": delhivery_gstin,
        "invoice_no": invoice_no,
        "basic_amount": basic_amount,
        "cgst": cgst,
        "sgst": sgst,
        "igst": igst,
        "total": total,
        "owner": owner,
    }


def build_excel(records, output_path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Freight Invoices"

    headers = [
        "Sr. No.", "Docket No.", "Month", "Date", "GST No.",
        "Invoice No.", "Name of the Party",
        "Basic Amount", "CGST", "SGST", "IGST", "Total", "Owner"
    ]

    # Header style
    header_fill = PatternFill("solid", fgColor="1F4E79")
    header_font = Font(bold=True, color="FFFFFF", size=11)
    center = Alignment(horizontal="center", vertical="center")
    thin = Side(style="thin", color="000000")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    for col_idx, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = center
        cell.border = border

    ws.row_dimensions[1].height = 20

    # Alternating row colours
    fill_even = PatternFill("solid", fgColor="DCE6F1")
    fill_odd = PatternFill("solid", fgColor="FFFFFF")
    data_font = Font(size=10)

    for row_idx, rec in enumerate(records, 2):
        fill = fill_even if row_idx % 2 == 0 else fill_odd
        row_data = [
            row_idx - 1,
            rec["lr_no"],
            rec["month"],
            rec["date"],
            rec["gstin"],
            rec["invoice_no"],
            "DELHIVERY LIMITED",
            rec["basic_amount"],
            rec["cgst"],
            rec["sgst"],
            rec["igst"],
            rec["total"],
            rec["owner"],
        ]
        for col_idx, value in enumerate(row_data, 1):
            cell = ws.cell(row=row_idx, column=col_idx, value=value)
            cell.fill = fill
            cell.font = data_font
            cell.border = border
            if col_idx in (8, 9, 10, 11, 12):  # numeric columns
                cell.number_format = "#,##0.00"
                cell.alignment = Alignment(horizontal="right")
            else:
                cell.alignment = Alignment(horizontal="center")

    # Auto-fit column widths
    col_widths = [8, 14, 10, 14, 20, 22, 22, 14, 10, 10, 10, 12, 10]
    for col_idx, width in enumerate(col_widths, 1):
        ws.column_dimensions[ws.cell(row=1, column=col_idx).column_letter].width = width

    # Freeze header row
    ws.freeze_panes = "A2"

    wb.save(output_path)


def main():
    pdf_files = sorted([
        f for f in os.listdir(OUTPUT_DIR) if f.lower().endswith(".pdf")
    ])

    if not pdf_files:
        print(f"No PDFs found in {OUTPUT_DIR}")
        return

    print(f"Found {len(pdf_files)} PDFs. Extracting data...\n")

    records = []
    errors = []

    for filename in pdf_files:
        pdf_path = os.path.join(OUTPUT_DIR, filename)
        try:
            data = extract_data(pdf_path)
            records.append(data)
            print(f"  OK  {filename} | LR: {data['lr_no']} | {data['invoice_no']} | "
                  f"{data['date']} | Total: {data['total']} | Owner: {data['owner']}")
        except Exception as e:
            errors.append(filename)
            print(f"  ERR {filename}: {e}")

    excel_path = os.path.join(os.path.dirname(OUTPUT_DIR), "freight_invoices.xlsx")
    build_excel(records, excel_path)

    print(f"\nDone! {len(records)} records written to: {excel_path}")
    if errors:
        print(f"Failed to parse {len(errors)} files: {errors}")


if __name__ == "__main__":
    main()
