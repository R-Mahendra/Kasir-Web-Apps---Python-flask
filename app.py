import json, datetime, io
from decimal import Decimal
from flask import Flask, send_file, render_template, request, session, jsonify
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader


app = Flask(__name__)
app.secret_key = "ZhaenxSecret"

PAJAK = Decimal("0.10")
DISKON = Decimal("0.10")


@app.route("/")
def index():
    cart = session.get("jumlahcart", [])
    return render_template("index.html", menu=menu, cart=cart)


# ===================================== LOAD DATA JSON (API)
def load_menu():
    try:
        with open("data/menu.json", "r", encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError:
        app.logger.error("menu.json not found")
        return {}
    except json.JSONDecodeError:
        app.logger.error("Invalid JSON in menu.json")
        return {}


menu = load_menu()


# ===================================== HELPER FUNCTIONS
def hitung_total(subtotal):
    subtotal = Decimal(str(subtotal))
    diskon = int(subtotal * DISKON)
    dpp = subtotal - diskon
    ppn = int(dpp * PAJAK)
    total = dpp + ppn
    return int(diskon), int(ppn), int(total)


def calculate_totals(cart):
    subtotal = sum(int(item["price"]) * int(item["qty"]) for item in cart)
    diskon, ppn, total = hitung_total(subtotal)
    return subtotal, diskon, ppn, total


def find_item_in_cart(cart, item_id):
    for item in cart:
        if str(item["id"]) == str(item_id):
            return item
    return None


def find_menu_item(item_id):
    for kategori, items in menu.items():
        for m in items:
            if str(m["id"]) == str(item_id):
                return m
    return None


def update_session_cart(cart):
    session["jumlahcart"] = cart
    session["cart_count"] = sum(i["qty"] for i in cart)
    session.modified = True


# ===================================== ROUTES
@app.route("/cart/update", methods=["POST"])
def cart_update():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid request"}), 400

        action = data.get("action")
        item_id = data.get("id")

        if not action or item_id is None:
            return jsonify({"error": "Missing parameters"}), 400

        cart = session.get("jumlahcart", [])
        target = find_item_in_cart(cart, item_id)

        # Handle ADD
        if action == "add":
            if not target:
                menu_item = find_menu_item(item_id)
                if not menu_item:
                    return jsonify({"error": "Item not found"}), 404

                cart.append(
                    {
                        "id": menu_item["id"],
                        "nama": menu_item["nama"],
                        "price": menu_item["price"],
                        "img": menu_item["img"],
                        "qty": 1,
                        "subtotal": menu_item["price"],
                    }
                )
            else:
                target["qty"] += 1
                target["subtotal"] = target["qty"] * target["price"]

        # Handle PLUS
        elif action == "plus":
            if not target:
                return jsonify({"error": "Item not in cart"}), 404
            target["qty"] += 1
            target["subtotal"] = target["qty"] * target["price"]

        # Handle MINUS
        elif action == "minus":
            if not target:
                return jsonify({"error": "Item not in cart"}), 404
            target["qty"] -= 1
            if target["qty"] <= 0:
                cart.remove(target)
            else:
                target["subtotal"] = target["qty"] * target["price"]

        # Handle REMOVE
        elif action == "remove":
            if not target:
                return jsonify({"error": "Item not in cart"}), 404
            cart.remove(target)

        else:
            return jsonify({"error": "Invalid action"}), 400

        update_session_cart(cart)
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

    except Exception as e:
        app.logger.error(f"Error in cart_update: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500


@app.route("/checkout", methods=["POST"])
def checkout():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid request"}), 400

        nama = data.get("nama", "").strip()
        if not nama:
            return jsonify({"error": "Nama tidak boleh kosong"}), 400

        try:
            cash = int(data.get("cash", 0))
        except (ValueError, TypeError):
            return jsonify({"error": "Jumlah uang tidak valid"}), 400

        cart = session.get("jumlahcart", [])
        if not cart:
            return jsonify({"error": "Keranjang kosong"}), 400

        subtotal = sum(int(item["price"]) * int(item["qty"]) for item in cart)
        diskon, ppn, total = hitung_total(subtotal)

        if cash < total:
            return (
                jsonify(
                    {
                        "error": f"Uang tidak cukup. Total: Rp {total:,}, Uang: Rp {cash:,}"
                    }
                ),
                400,
            )

        kembalian = cash - total

        session["pembeli"] = {
            "nama": nama,
            "cash": cash,
            "subtotal": subtotal,
            "ppn": ppn,
            "diskon": diskon,
            "total": total,
            "kembalian": kembalian,
        }
        session.modified = True

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

    except Exception as e:
        app.logger.error(f"Error in checkout: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500


@app.route("/cart/clear", methods=["POST"])
def cart_clear():
    session["jumlahcart"] = []
    session["cart_count"] = 0
    session.modified = True
    return jsonify({"success": True})


@app.route("/download_struk", methods=["POST"])
def download_struk():
    try:
        cart = session.get("jumlahcart", [])
        if not cart:
            return jsonify({"error": "Keranjang kosong"}), 400

        data = request.get_json()
        nama = data.get("nama", "").strip()

        try:
            cash = int(data.get("cash", 0))
        except (ValueError, TypeError):
            return jsonify({"error": "Jumlah uang tidak valid"}), 400

        # Hitung total
        subtotal = sum(item["price"] * item["qty"] for item in cart)
        diskon, ppn, total = hitung_total(subtotal)
        kembalian = cash - total

        if cash < total:
            return jsonify({"error": "Uang tidak cukup"}), 400

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
        except Exception as e:
            app.logger.warning(f"Logo not found: {str(e)}")

        pdf.setFont("Helvetica", 10)
        pdf.drawCentredString(
            300,
            695,
            "Cikarang Square, Jl. Cibarusah Raya No.168, Pasirsari, "
            "Cikarang Sel, Kab.Bekasi, Jawa Barat 17550",
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
            pdf.drawRightString(550, y, f"Rp {item['price'] * item['qty']:,}")
            y -= 20

            # Check if need new page
            if y < 100:
                pdf.showPage()
                y = 750

        pdf.line(40, y, 550, y)
        y -= 25

        # ===== TOTAL =====
        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawString(40, y, "Subtotal:")
        pdf.drawRightString(550, y, f"Rp {subtotal:,}")
        y -= 20

        pdf.drawString(40, y, "Diskon 10%:")
        pdf.drawRightString(550, y, f"Rp {diskon:,}")
        y -= 20

        pdf.drawString(40, y, "PPN 10%:")
        pdf.drawRightString(550, y, f"Rp {ppn:,}")
        y -= 20

        pdf.drawString(40, y, "Total:")
        pdf.drawRightString(550, y, f"Rp {total:,}")
        y -= 20

        pdf.drawString(40, y, "Uang Bayar:")
        pdf.drawRightString(550, y, f"Rp {cash:,}")
        y -= 20

        pdf.drawString(40, y, "Kembalian:")
        pdf.drawRightString(550, y, f"Rp {kembalian:,}")
        y -= 50

        pdf.drawString(40, y, "_" * 76)
        y -= 20
        pdf.drawString(200, y, "Terimakasih sudah berkunjung.")

        pdf.showPage()
        pdf.save()

        buffer.seek(0)

        # AUTO FILENAME
        tanggal = datetime.datetime.now().strftime("%d-%m-%Y")
        fileDownload = f"struk-{tanggal}.pdf"

        return send_file(
            buffer,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=fileDownload,
        )

    except Exception as e:
        app.logger.error(f"Error in download_struk: {str(e)}")
        return jsonify({"error": "Gagal membuat struk"}), 500


@app.route("/cart/get", methods=["GET"])
def cart_get():
    """Get current cart from session"""
    try:
        cart = session.get("jumlahcart", [])
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
    except Exception as e:
        app.logger.error(f"Error in cart_get: {str(e)}")


if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)
