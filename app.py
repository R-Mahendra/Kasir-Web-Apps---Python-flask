import json, io, datetime
from flask import Flask, send_file, render_template, request, session, jsonify
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader

app = Flask(__name__)
app.secret_key = "ZhaenxSecret"  # cookie


# ===================================== LOAD MENU SEKALI SAJA (GLOBAL)
with open("data/menu.json", "r", encoding="utf-8") as file:
    menu = json.load(file)

# ============= CONFIG =============
PAJAK = 0.10  # 10%
DISKON = 0.10  # 10%


# =====================================
def hitung_total(subtotal):
    diskon = int(subtotal * DISKON)  # 10% dari subtotal
    dpp = subtotal - diskon  # harga setelah diskon
    ppn = int(dpp * PAJAK)  # pajak setelah diskon
    total = dpp + ppn
    return diskon, ppn, total


# HITUNG TOTAL OTOMATIS CART
def calculate_totals(cart):
    subtotal = sum(int(item["price"]) * int(item["qty"]) for item in cart)
    diskon, ppn, total = hitung_total(subtotal)
    return subtotal, diskon, ppn, total


@app.route("/cart/update", methods=["POST"])
def cart_update():
    data = request.get_json()
    action = data.get("action")
    item_id = str(data.get("id"))

    cart = session.get("jumlahcart", [])

    # cari item di cart
    target = None
    for item in cart:
        if str(item["id"]) == item_id:
            target = item
            break

    # handle ADD
    if action == "add":
        if not target:
            # cari data di menu.json
            for kategori, items in menu.items():
                for m in items:
                    if str(m["id"]) == item_id:
                        cart.append(
                            {
                                "id": m["id"],
                                "nama": m["nama"],
                                "price": m["price"],
                                "img": m["img"],
                                "qty": 1,
                                "subtotal": m["price"],
                            }
                        )
                        break
        else:
            target["qty"] += 1
            target["subtotal"] = target["qty"] * target["price"]

    # handle PLUS
    if action == "plus" and target:
        target["qty"] += 1
        target["subtotal"] = target["qty"] * target["price"]

    # handle MINUS
    if action == "minus" and target:
        target["qty"] -= 1
        if target["qty"] <= 0:
            cart.remove(target)
        else:
            target["subtotal"] = target["qty"] * target["price"]

    # handle REMOVE
    if action == "remove" and target:
        cart.remove(target)

    session["jumlahcart"] = cart
    session["cart_count"] = sum(i["qty"] for i in cart)

    subtotal, diskon, ppn, total = calculate_totals(cart)

    return jsonify(
        {
            "cart": cart,
            "count": sum(i["qty"] for i in cart),
            "subtotal": subtotal,
            "diskon": diskon,
            "ppn": ppn,
            "total": total,
        }
    )


@app.route("/checkout", methods=["POST"])
def checkout():
    data = request.get_json()

    nama = data.get("nama")
    cash = int(data.get("cash", 0))

    cart = session.get("jumlahcart", [])

    # Hitung subtotal
    subtotal = 0
    for item in cart:
        subtotal += int(item["price"]) * int(item["qty"])

    diskon, ppn, total = hitung_total(subtotal)

    kembalian = cash - total

    # SIMPAN SEMENTARA KE SESSION (opsional)
    session["pembeli"] = {
        "nama": nama,
        "cash": cash,
        "subtotal": subtotal,
        "ppn": ppn,
        "diskon": diskon,
        "total": total,
        "kembalian": kembalian,
    }

    return jsonify(
        {
            "nama": nama,
            "cash": cash,
            "subtotal": subtotal,
            "ppn": ppn,
            "diskon": diskon,
            "total": total,
            "kembalian": kembalian,
        }
    )


@app.route("/cart/clear", methods=["POST"])
def cart_clear():
    session["jumlahcart"] = []
    session["cart_count"] = 0
    return jsonify({"success": True})


@app.route("/download_struk", methods=["POST"])
def download_struk():
    cart = session.get("jumlahcart", [])
    nama = request.json.get("nama")
    cash = int(request.json.get("cash", 0))

    # Hitung total
    subtotal = sum(item["price"] * item["qty"] for item in cart)
    diskon, ppn, total = hitung_total(subtotal)
    kembalian = cash - total

    # Membuat PDF ke memory (buffer)
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)

    # ===== HEADER =====
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawCentredString(300, 725, "Restoran Kelompok 4")

    # LOGO
    try:
        logo = ImageReader("static/img/logo.png")
        pdf.drawImage(
            logo, (595 / 2) - 40, 750, width=80, height=80, preserveAspectRatio=True
        )
    except:
        pass

    pdf.setFont("Helvetica", 10)
    pdf.drawCentredString(
        300,
        695,
        "Cikarang Square, Jl. Cibarusah Raya No.168, Pasirsari, Cikarang Sel, Kab.Bekasi, Jawa Barat 17550",
    )

    pdf.drawCentredString(
        290, 682, f"Tanggal: {datetime.datetime.now().strftime('%d-%m-%Y %H:%M')}"
    )

    pdf.line(40, 670, 550, 670)

    # ===== BODY =====
    y = 650
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(40, y, f"Nama Pembeli: {nama}")
    y -= 25

    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(40, y, "Daftar Pembelian:")
    y -= 20

    pdf.setFont("Helvetica", 11)

    for item in cart:
        pdf.drawString(40, y, f"{item['nama']}  x{item['qty']}")
        pdf.drawRightString(550, y, f"Rp {item['price'] * item['qty']:,.2f}")
        y -= 20

    pdf.line(40, y, 550, y)
    y -= 25

    # ===== TOTAL =====
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(40, y, "Subtotal:")
    pdf.drawRightString(550, y, f"Rp {subtotal:,.2f}")
    y -= 20

    pdf.drawString(40, y, "Diskon 10%:")
    pdf.drawRightString(550, y, f"Rp {diskon:,.2f}")
    y -= 20

    pdf.drawString(40, y, "PPN 10%:")
    pdf.drawRightString(550, y, f"Rp {ppn:,.2f}")
    y -= 20

    pdf.drawString(40, y, "Total:")
    pdf.drawRightString(550, y, f"Rp {total:,.2f}")
    y -= 20

    pdf.drawString(40, y, "Uang Bayar:")
    pdf.drawRightString(550, y, f"Rp {cash:,.2f}")
    y -= 20

    pdf.drawString(40, y, "Kembalian:")
    pdf.drawRightString(550, y, f"Rp {kembalian:,.2f}")
    y -= 50

    pdf.drawString(40, y, "_" * 76)
    y -= 20
    pdf.drawString(200, y, "Terimakasih sudah berkunjung.")

    pdf.showPage()
    pdf.save()

    buffer.seek(0)

    # AUTO FILENAME: struk-tanggal-bulan-tahun.pdf
    tanggal = datetime.datetime.now().strftime(("%d-%m-%Y"))
    fileDownload = f"struk-{tanggal}.pdf"

    return send_file(
        buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=fileDownload,
    )


@app.route("/")
def index():
    cart = session.get("jumlahcart", [])
    return render_template("index.html", menu=menu, cart=cart)


if __name__ == "__main__":
    app.run(debug=True)
