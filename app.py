import json
import io
import datetime
from decimal import Decimal
from flask import Flask, send_file, render_template, request, session, jsonify
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader


# ========================================================================
# INISIALISASI APLIKASI FLASK
# ========================================================================

# Import Flask untuk membuat web application
app = Flask(__name__)

# Secret key untuk enkripsi session cookies
# Digunakan untuk sign data session agar tidak bisa dimanipulasi oleh client
# Harus random dan rahasia untuk keamanan aplikasi
# Key ini di-generate menggunakan cryptographic random generator
app.secret_key = "53616c7465645f5ff22da9cb2932309bc5d27f5fb2f59d57bca3150476f82a19"


@app.route("/")
def index():
    # Ambil data cart dari session.
    # Kalau belum ada, default-nya list kosong.
    cart = session.get("jumlahcart", [])

    # Render halaman index.html
    # Kirim data menu dan cart ke template
    return render_template("index.html", menu=menu, cart=cart)


# ========================================================================
# KONSTANTA APLIKASI
# ========================================================================

# Konstanta untuk perhitungan pajak dan diskon
# Menggunakan Decimal untuk akurasi tinggi dalam perhitungan finansial
# Float memiliki masalah precision: 0.1 + 0.2 != 0.3
# Decimal mengatasi masalah ini dan cocok untuk financial calculation

PAJAK = Decimal("0.10")  # PPN 10% sesuai regulasi perpajakan Indonesia
DISKON = Decimal("0.10")  # Diskon promosi 10% untuk semua transaksi


# ========================================================================
# LOAD DATA MENU DARI FILE JSON
# ========================================================================


def load_menu():
    """
    Memuat data menu dari file JSON dengan error handling yang robust

    Fungsi ini dipanggil sekali saat aplikasi start untuk load semua data menu
    dari file eksternal (data/menu.json) ke dalam memory

    Returns:
        dict: Dictionary berisi data menu yang sudah di-parse dari JSON
              Format: {"kategori": [{"id": 1, "nama": "...", "price": ...}, ...]}
        dict: Dictionary kosong {} jika terjadi error (file tidak ada atau invalid)

    Error Handling:
        - FileNotFoundError: File menu.json tidak ditemukan
        - JSONDecodeError: Syntax error di file JSON (koma kurang, quote salah, dll)
    """
    try:
        # Buka file menu.json dengan mode read
        # encoding="utf-8" untuk support karakter Indonesia (é, ñ, dll)
        # Context manager (with) otomatis close file setelah selesai
        with open("data/menu.json", "r", encoding="utf-8") as file:
            # Parse JSON string menjadi Python dictionary
            # json.load() membaca file dan convert ke dict/list Python
            return json.load(file)

    except FileNotFoundError:
        # Exception ini muncul jika file tidak ditemukan
        # Bisa karena path salah atau file memang tidak ada

        # Log error ke console/file untuk debugging
        # Penting untuk troubleshooting di production environment
        app.logger.error("menu.json not found")

        # Return empty dict agar aplikasi tidak crash
        # Aplikasi tetap bisa jalan, hanya menu-nya kosong
        return {}

    except json.JSONDecodeError:
        # Exception ini muncul jika file JSON tidak valid
        # Contoh: ada koma yang kurang, bracket tidak closing, dll

        # Log error untuk debugging
        app.logger.error("Invalid JSON in menu.json")

        # Return empty dict agar aplikasi tidak crash
        return {}


# Execute fungsi load_menu() saat aplikasi start
# Variable global 'menu' ini akan digunakan di seluruh aplikasi
# Load sekali saja untuk efisiensi (tidak load ulang setiap request)
menu = load_menu()


# ========================================================================
# HELPER FUNCTIONS - PERHITUNGAN FINANSIAL
# ========================================================================


def hitung_total(subtotal):
    """
    Menghitung diskon, PPN, dan total akhir berdasarkan subtotal

    Alur perhitungan sesuai aturan perpajakan Indonesia:
    1. Hitung diskon dari subtotal
    2. Kurangi subtotal dengan diskon = DPP (Dasar Pengenaan Pajak)
    3. Hitung PPN dari DPP (BUKAN dari subtotal!)
    4. Total = DPP + PPN

    Args:
        subtotal (int/float): Total harga semua item sebelum diskon dan pajak

    Returns:
        tuple: (diskon, ppn, total) - semua dalam format integer (Rupiah)

    Contoh:
        subtotal = 100000
        diskon, ppn, total = hitung_total(100000)
        # diskon = 10000 (10% dari 100000)
        # dpp = 90000 (100000 - 10000)
        # ppn = 9000 (10% dari 90000)
        # total = 99000 (90000 + 9000)
    """

    # Konversi subtotal ke Decimal untuk perhitungan akurat
    # str() diperlukan untuk menghindari floating point error
    # Decimal("100.50") lebih akurat dari Decimal(100.50)
    subtotal = Decimal(str(subtotal))

    # STEP 1: Hitung diskon 10% dari subtotal
    # Contoh: Rp 100.000 × 10% = Rp 10.000
    # int() untuk convert ke integer karena Rupiah tidak ada sen
    diskon = int(subtotal * DISKON)

    # STEP 2: Hitung DPP (Dasar Pengenaan Pajak)
    # DPP = Subtotal dikurangi diskon
    # Ini adalah harga yang akan dikenakan pajak
    # Contoh: Rp 100.000 - Rp 10.000 = Rp 90.000
    dpp = subtotal - diskon

    # STEP 3: Hitung PPN 10% dari DPP (PENTING: dari DPP, bukan subtotal!)
    # Sesuai aturan perpajakan, pajak dihitung SETELAH diskon
    # Contoh: Rp 90.000 × 10% = Rp 9.000
    ppn = int(dpp * PAJAK)

    # STEP 4: Hitung total yang harus dibayar
    # Total = DPP + PPN (harga setelah diskon + pajak)
    # Contoh: Rp 90.000 + Rp 9.000 = Rp 99.000
    total = dpp + ppn

    # Return tuple berisi 3 nilai: diskon, ppn, dan total
    # Semua di-convert ke int karena Rupiah tidak menggunakan desimal
    return int(diskon), int(ppn), int(total)


def calculate_totals(cart):
    """
    Menghitung semua total yang ada di keranjang belanja

    Fungsi wrapper yang menggabungkan:
    1. Perhitungan subtotal dari semua item di cart
    2. Perhitungan diskon, PPN, dan total menggunakan hitung_total()

    Args:
        cart (list): List of dictionaries, setiap item memiliki keys:
                    - id: ID unik item
                    - nama: Nama menu
                    - price: Harga per item
                    - qty: Jumlah quantity yang dipesan
                    - subtotal: price × qty

    Returns:
        tuple: (subtotal, diskon, ppn, total) - semua dalam integer

    Contoh cart:
        [
            {"id": 1, "nama": "Nasi Goreng", "price": 25000, "qty": 2, "subtotal": 50000},
            {"id": 2, "nama": "Es Teh", "price": 5000, "qty": 3, "subtotal": 15000}
        ]

        Hasil:
        subtotal = 65000  (50000 + 15000)
        diskon = 6500     (10% dari 65000)
        ppn = 5850        (10% dari 58500)
        total = 64350     (58500 + 5850)
    """

    # Hitung subtotal dengan cara:
    # 1. Loop setiap item di cart
    # 2. Kalikan price × qty untuk setiap item
    # 3. Jumlahkan semua hasil perkalian menggunakan sum()
    #
    # Generator expression (... for item in cart) lebih efisien dari loop biasa
    # karena tidak membuat list intermediate di memory
    #
    # Contoh:
    # Item 1: 25000 × 2 = 50000
    # Item 2: 5000 × 3 = 15000
    # Subtotal = 50000 + 15000 = 65000
    subtotal = sum(int(item["price"]) * int(item["qty"]) for item in cart)

    # Panggil fungsi hitung_total untuk mendapatkan diskon, ppn, dan total
    # Fungsi ini menerapkan semua logic perpajakan yang kompleks
    diskon, ppn, total = hitung_total(subtotal)

    # Return semua nilai dalam satu tuple
    # Tuple ini akan di-unpack di tempat lain untuk update display
    return subtotal, diskon, ppn, total


# ========================================================================
# HELPER FUNCTIONS - PENCARIAN DATA
# ========================================================================


def find_item_in_cart(cart, item_id):
    """
    Mencari item di keranjang belanja berdasarkan ID

    Fungsi ini digunakan untuk operasi:
    - PLUS: Cari item dulu sebelum tambah qty
    - MINUS: Cari item dulu sebelum kurangi qty
    - REMOVE: Cari item dulu sebelum hapus dari cart

    Args:
        cart (list): List of items dalam cart (dari session)
        item_id (str/int): ID item yang ingin dicari

    Returns:
        dict: Reference ke item yang ditemukan (bukan copy!)
              Item memiliki keys: id, nama, price, qty, subtotal, img
        None: Jika item dengan ID tersebut tidak ada di cart

    Important Notes:
        - Return adalah REFERENCE, bukan copy
        - Perubahan pada return value akan affect cart langsung
        - Tidak perlu save lagi ke session setelah modify

    Contoh penggunaan:
        item = find_item_in_cart(cart, "5")
        if item:
            item["qty"] += 1  # Langsung mengubah qty di cart
            item["subtotal"] = item["qty"] * item["price"]
        else:
            print("Item tidak ditemukan")
    """

    # Loop setiap item yang ada di keranjang
    for item in cart:
        # Bandingkan ID sebagai string untuk menghindari type mismatch
        # ID bisa datang sebagai:
        # - int dari JSON parsing ({"id": 5})
        # - string dari form POST (request.form["id"] = "5")
        #
        # Dengan convert keduanya ke string, kita pastikan perbandingan akurat
        # str(5) == str("5") → "5" == "5" → True
        if str(item["id"]) == str(item_id):
            # Item ditemukan!
            # Return reference ke item (bukan copy)
            # Ini adalah Python feature: objects di-pass by reference
            return item

    # Loop selesai tapi tidak ada yang match
    # Return None untuk indicate "not found"
    # Caller bisa cek dengan: if item: atau if item is None:
    return None


def find_menu_item(item_id):
    """
    Mencari item di database menu berdasarkan ID

    Fungsi ini dipanggil saat user klik "Add to Cart"
    Kita hanya punya ID dari button, perlu ambil data lengkap dari menu database

    Args:
        item_id (str/int): ID item yang ingin dicari

    Returns:
        dict: Data item lengkap dari menu dengan keys:
              - id: ID unik item
              - nama: Nama menu
              - price: Harga per item
              - img: Path ke gambar menu
              - kategori: Kategori menu (optional)
        None: Jika item tidak ditemukan di database menu

    Struktur menu database:
        {
            "makanan": [
                {"id": 1, "nama": "Nasi Goreng", "price": 25000, "img": "nasi_goreng.jpg"},
                {"id": 2, "nama": "Mie Goreng", "price": 20000, "img": "mie_goreng.jpg"}
            ],
            "minuman": [
                {"id": 10, "nama": "Es Teh", "price": 5000, "img": "es_teh.jpg"},
                {"id": 11, "nama": "Es Jeruk", "price": 7000, "img": "es_jeruk.jpg"}
            ],
            "snack": [...]
        }

    Contoh penggunaan:
        menu_data = find_menu_item("1")
        if menu_data:
            cart.append({
                "id": menu_data["id"],
                "nama": menu_data["nama"],
                "price": menu_data["price"],
                "img": menu_data["img"],
                "qty": 1
            })
    """

    # Loop setiap kategori di menu
    # menu.items() return tuples: ("makanan", [...]), ("minuman", [...])
    # kategori = "makanan", items = list of menu items
    for kategori, items in menu.items():

        # Loop setiap item dalam kategori tersebut
        # m = menu item dictionary
        for m in items:
            # Bandingkan ID sebagai string (alasan sama seperti find_item_in_cart)
            if str(m["id"]) == str(item_id):
                # Item ditemukan!
                # Return seluruh data item dari database menu
                # Data ini akan digunakan untuk populate cart
                return m

    # Item tidak ditemukan di semua kategori
    # Return None untuk indicate "not found"
    # Ini bisa terjadi jika:
    # - ID invalid/tidak ada di database
    # - Menu database corrupt
    # - Ada bug di frontend yang kirim ID salah
    return None


# ========================================================================
# HELPER FUNCTION - UPDATE SESSION CART
# ========================================================================


def update_session_cart(cart):
    """
    Menyimpan cart ke session dan menghitung total quantity

    Fungsi ini dipanggil setiap kali ada perubahan pada cart untuk:
    1. Persist data ke server-side session
    2. Menghitung total items untuk badge counter
    3. Mark session sebagai modified (penting untuk Flask session)

    Args:
        cart (list): List of dictionaries berisi items di cart

    Important Notes:
        - session.modified = True WAJIB dipanggil
        - Tanpa ini, perubahan pada list/dict tidak akan tersimpan
        - Ini adalah common pitfall dalam Flask session management
    """

    # Simpan cart ke session dengan key "jumlahcart"
    # Data ini akan persist selama session aktif (hingga browser close)
    session["jumlahcart"] = cart

    # Hitung total quantity dari semua item untuk badge counter
    # sum() dengan generator expression lebih efisien daripada loop
    # Contoh: jika cart punya 3 items dengan qty [2, 1, 3]
    # maka cart_count = 2 + 1 + 3 = 6
    session["cart_count"] = sum(i["qty"] for i in cart)

    # CRITICAL: Mark session as modified
    # Flask session menggunakan signed cookies yang hanya diupdate jika modified
    # Tanpa ini, perubahan pada mutable objects (list/dict) tidak tersimpan
    # Ini adalah best practice untuk semua session modifications
    session.modified = True


# ========================================================================
# API ENDPOINT - CART UPDATE
# ========================================================================


@app.route("/cart/update", methods=["POST"])
def cart_update():
    """
    Endpoint untuk menangani semua operasi pada cart

    Supported Actions:
        - "add": Tambah item baru atau increase qty jika sudah ada
        - "plus": Increase quantity item yang sudah ada
        - "minus": Decrease quantity, auto-remove jika qty = 0
        - "remove": Hapus item dari cart (regardless of qty)

    Request Body (JSON):
        {
            "action": "add|plus|minus|remove",
            "id": "item_id"
        }

    Response (JSON):
        Success (200):
        {
            "cart": [...],           # Updated cart data
            "count": 5,              # Total quantity for badge
            "subtotal": 100000,      # Total sebelum diskon
            "diskon": 10000,         # Potongan harga
            "ppn": 9000,             # Pajak
            "total": 99000           # Total akhir
        }

        Error (400/404/500):
        {
            "error": "Error message"
        }

    HTTP Status Codes:
        200: Success
        400: Bad request (invalid input)
        404: Item not found
        500: Internal server error
    """

    try:
        # ============================================================
        # STEP 1: VALIDASI REQUEST & EXTRACT PARAMETERS
        # ============================================================

        # Parse JSON dari request body
        # request.get_json() return None jika:
        # - Request tidak mengandung JSON
        # - Content-Type header bukan application/json
        # - JSON syntax error (invalid format)
        data = request.get_json()

        # Validasi: pastikan request body mengandung JSON
        # Return 400 Bad Request jika tidak ada data
        if not data:
            return jsonify({"error": "Invalid request"}), 400

        # Extract action dan item_id dari JSON payload
        # .get() method return None jika key tidak ada (safe)
        action = data.get("action")  # Expected: "add"|"plus"|"minus"|"remove"
        item_id = data.get("id")  # Expected: string atau integer ID

        # Validasi: pastikan parameter wajib tersedia
        # action harus ada dan tidak empty string
        # item_id harus ada (boleh 0, tapi tidak boleh None)
        if not action or item_id is None:
            return jsonify({"error": "Missing parameters"}), 400

        # ============================================================
        # STEP 2: LOAD CART & FIND TARGET ITEM
        # ============================================================

        # Ambil cart dari session
        # Default ke empty list jika:
        # - Session baru (first time user)
        # - Cart sudah di-clear sebelumnya
        # - Session expired dan di-reset
        cart = session.get("jumlahcart", [])

        # Cari apakah item dengan ID ini sudah ada di cart
        # find_item_in_cart return:
        # - Reference ke item dict jika ada (modifiable)
        # - None jika tidak ada
        target = find_item_in_cart(cart, item_id)

        # ============================================================
        # STEP 3: HANDLE ACTION - ADD
        # ============================================================

        if action == "add":
            # ADD action punya 2 skenario berbeda

            # SKENARIO 1: Item BELUM ada di cart (target = None)
            if not target:
                # Item baru, perlu ambil data lengkap dari menu database
                menu_item = find_menu_item(item_id)

                # Validasi: pastikan item exists di menu
                # Bisa tidak ada jika:
                # - ID invalid/typo
                # - Item sudah dihapus dari menu
                # - Bug di frontend yang kirim ID salah
                if not menu_item:
                    return jsonify({"error": "Item not found"}), 404

                # Buat dictionary baru untuk item
                # Copy data dari menu_item dan tambah qty & subtotal
                cart.append(
                    {
                        "id": menu_item["id"],  # ID unik item
                        "nama": menu_item["nama"],  # Nama menu
                        "price": menu_item["price"],  # Harga per item
                        "img": menu_item["img"],  # Path gambar
                        "qty": 1,  # Quantity awal = 1
                        "subtotal": menu_item["price"],  # price × qty = price × 1
                    }
                )

            # SKENARIO 2: Item SUDAH ada di cart (target != None)
            else:
                # Tinggal tambah quantity dan update subtotal
                # target adalah reference, jadi modifikasi langsung affect cart
                target["qty"] += 1
                target["subtotal"] = target["qty"] * target["price"]

        # ============================================================
        # STEP 4: HANDLE ACTION - PLUS
        # ============================================================

        elif action == "plus":
            # PLUS hanya bisa dilakukan pada item yang SUDAH ada
            # Validasi: jika item tidak ada, return error
            # Seharusnya tidak terjadi karena button plus hanya muncul di cart
            # Tapi kita tetap validate untuk robustness
            if not target:
                return jsonify({"error": "Item not in cart"}), 404

            # Tambah quantity dan update subtotal
            # Logic sama dengan ADD skenario 2
            target["qty"] += 1
            target["subtotal"] = target["qty"] * target["price"]

        # ============================================================
        # STEP 5: HANDLE ACTION - MINUS
        # ============================================================

        elif action == "minus":
            # MINUS juga hanya untuk item yang sudah ada
            if not target:
                return jsonify({"error": "Item not in cart"}), 404

            # Kurangi quantity
            target["qty"] -= 1

            # CRITICAL LOGIC: Auto-remove jika qty = 0
            # Ini memberikan UX yang baik:
            # - User tidak perlu klik remove button terpisah
            # - Tinggal tekan minus sampai item hilang
            # - Lebih intuitive untuk mobile users
            if target["qty"] <= 0:
                # Hapus item dari cart
                # cart.remove() mencari dan menghapus object dari list
                cart.remove(target)
            else:
                # Qty masih positif, update subtotal
                target["subtotal"] = target["qty"] * target["price"]

        # ============================================================
        # STEP 6: HANDLE ACTION - REMOVE
        # ============================================================

        elif action == "remove":
            # REMOVE menghapus item regardless of quantity
            # Validasi: item harus ada
            if not target:
                return jsonify({"error": "Item not in cart"}), 404

            # Hapus item dari cart
            # Tidak peduli qty-nya berapa, langsung dihapus
            # Di frontend ada confirmation dialog untuk prevent accidental delete
            cart.remove(target)

        # ============================================================
        # STEP 7: HANDLE INVALID ACTION
        # ============================================================

        else:
            # Action tidak dikenali (bukan add/plus/minus/remove)
            # Ini defensive programming - jangan assume input selalu valid
            # Bisa terjadi jika:
            # - Typo di frontend code
            # - Malicious request
            # - API misuse
            return jsonify({"error": "Invalid action"}), 400

        # ============================================================
        # STEP 8: UPDATE SESSION & CALCULATE TOTALS
        # ============================================================

        # Simpan cart yang sudah dimodifikasi ke session
        # Function ini juga menghitung cart_count untuk badge
        update_session_cart(cart)

        # Hitung semua total finansial untuk response
        # calculate_totals return tuple: (subtotal, diskon, ppn, total)
        subtotal, diskon, ppn, total = calculate_totals(cart)

        # ============================================================
        # STEP 9: RETURN SUCCESS RESPONSE
        # ============================================================

        # Return JSON response dengan semua data yang dibutuhkan frontend
        # Status code 200 (OK) adalah default untuk return tanpa error
        return jsonify(
            {
                "cart": cart,  # List lengkap items di cart
                "count": sum(i["qty"] for i in cart),  # Total qty untuk badge
                "subtotal": subtotal,  # Total sebelum diskon
                "diskon": diskon,  # Potongan harga
                "ppn": ppn,  # Pajak
                "total": total,  # Total akhir yang harus dibayar
            }
        )

    # ============================================================
    # EXCEPTION HANDLING
    # ============================================================

    except Exception as e:
        # Catch-all untuk unexpected errors
        # Contoh errors yang bisa terjadi:
        # - KeyError jika item structure tidak sesuai
        # - TypeError jika ada type mismatch
        # - Any runtime errors

        # Log error untuk debugging
        # Di production, log ini akan masuk ke file atau monitoring system
        app.logger.error(f"Error in cart_update: {str(e)}")

        # Return generic error message
        # JANGAN expose detail error ke client untuk security
        # Status code 500 = Internal Server Error
        return jsonify({"error": "Internal server error"}), 500


# ========================================================================
# API ENDPOINT - CHECKOUT
# ========================================================================


@app.route("/checkout", methods=["POST"])
def checkout():
    """
    Endpoint untuk memproses pembayaran

    Proses checkout meliputi:
    1. Validasi data pembeli (nama, cash)
    2. Validasi cart tidak kosong
    3. Hitung total pembayaran
    4. Validasi uang cukup
    5. Hitung kembalian
    6. Simpan data transaksi ke session
    7. Return rincian pembayaran

    Request Body (JSON):
        {
            "nama": "John Doe",
            "cash": 150000
        }

    Response (JSON):
        Success (200):
        {
            "nama": "John Doe",
            "cash": 150000,
            "subtotal": 100000,
            "ppn": 9000,
            "diskon": 10000,
            "total": 99000,
            "kembalian": 51000
        }

        Error (400):
        {
            "error": "Error message"
        }

    Validation Rules:
        - Nama: tidak boleh kosong atau hanya spasi
        - Cash: harus integer positif
        - Cart: minimal 1 item
        - Cash: harus >= total
    """

    try:
        # ============================================================
        # STEP 1: VALIDASI REQUEST & EXTRACT DATA
        # ============================================================

        # Parse JSON dari request body
        data = request.get_json()

        # Validasi: pastikan request mengandung JSON
        if not data:
            return jsonify({"error": "Invalid request"}), 400

        # ============================================================
        # STEP 2: VALIDASI NAMA PEMBELI
        # ============================================================

        # Extract nama pembeli
        # .get("nama", "") return empty string jika key tidak ada
        # .strip() remove leading/trailing whitespace
        nama = data.get("nama", "").strip()

        # Validasi: nama tidak boleh kosong
        # Empty string atau hanya spasi akan fail validation
        # Nama penting untuk:
        # - Identifikasi pembeli di struk
        # - Courtesy (sapaan ke customer)
        # - Audit trail jika perlu
        if not nama:
            return jsonify({"error": "Nama tidak boleh kosong"}), 400

        # ============================================================
        # STEP 3: VALIDASI JUMLAH UANG (CASH)
        # ============================================================

        try:
            # Convert cash ke integer
            # Rupiah tidak menggunakan desimal, jadi int sudah cukup
            # .get("cash", 0) return 0 jika key tidak ada
            cash = int(data.get("cash", 0))

        except (ValueError, TypeError):
            # ValueError: jika input bukan angka (contoh: "abc", "12.5abc")
            # TypeError: jika input adalah type yang tidak bisa di-convert

            # Return error message yang user-friendly
            # Jangan expose technical error (ValueError) ke user
            return jsonify({"error": "Jumlah uang tidak valid"}), 400

        # ============================================================
        # STEP 4: VALIDASI CART TIDAK KOSONG
        # ============================================================

        # Ambil cart dari session
        cart = session.get("jumlahcart", [])

        # Validasi: cart minimal harus punya 1 item
        # Empty cart bisa terjadi jika:
        # - User langsung akses /checkout tanpa shopping
        # - Session expired
        # - Cart di-clear tapi user masih di checkout page
        if not cart:
            return jsonify({"error": "Keranjang kosong"}), 400

        # ============================================================
        # STEP 5: HITUNG TOTAL PEMBAYARAN
        # ============================================================

        # Hitung subtotal dari semua item di cart
        # sum() dengan generator expression
        # Loop setiap item, kalikan price × qty, lalu jumlahkan
        subtotal = sum(int(item["price"]) * int(item["qty"]) for item in cart)

        # Hitung diskon, ppn, dan total akhir
        # Menggunakan helper function hitung_total()
        # yang mengapply semua logic perpajakan
        diskon, ppn, total = hitung_total(subtotal)

        # ============================================================
        # STEP 6: VALIDASI UANG CUKUP
        # ============================================================

        # Cek apakah cash yang diberikan >= total yang harus dibayar
        if cash < total:
            # Uang tidak cukup, return error dengan detail
            # Format angka dengan thousand separator (:,)
            # Contoh: 99000 → "99,000"
            # Ini memudahkan user untuk baca dan membandingkan
            return (
                jsonify(
                    {
                        "error": f"Uang tidak cukup. Total: Rp {total:,}, Uang: Rp {cash:,}"
                    }
                ),
                400,
            )

        # ============================================================
        # STEP 7: HITUNG KEMBALIAN
        # ============================================================

        # Kembalian = Uang yang diberikan - Total yang harus dibayar
        # Contoh: Rp 150.000 - Rp 99.000 = Rp 51.000
        kembalian = cash - total

        # ============================================================
        # STEP 8: SIMPAN DATA TRANSAKSI KE SESSION
        # ============================================================

        # Simpan semua data pembayaran ke session
        # Data ini akan digunakan untuk:
        # 1. Display rincian di halaman pembayaran
        # 2. Generate PDF struk
        # 3. Audit trail (bisa dipindah ke database nantinya)
        session["pembeli"] = {
            "nama": nama,  # Nama customer
            "cash": cash,  # Uang yang dibayar
            "subtotal": subtotal,  # Total sebelum diskon & pajak
            "ppn": ppn,  # Pajak 10%
            "diskon": diskon,  # Diskon 10%
            "total": total,  # Total akhir
            "kembalian": kembalian,  # Uang kembali
        }

        # CRITICAL: Mark session as modified
        # Tanpa ini, data pembeli tidak akan tersimpan
        session.modified = True

        # ============================================================
        # STEP 9: RETURN SUCCESS RESPONSE
        # ============================================================

        # Return semua data pembayaran ke frontend
        # Frontend akan display data ini di rincian pembayaran
        # dan enable tombol download struk
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

    # ============================================================
    # EXCEPTION HANDLING
    # ============================================================

    except Exception as e:
        # Catch-all untuk unexpected errors
        # Log error untuk debugging
        app.logger.error(f"Error in checkout: {str(e)}")

        # Return generic error message
        # Jangan expose detail error untuk security
        return jsonify({"error": "Internal server error"}), 500


# ========================================================================
# API ENDPOINT - CLEAR CART
# ========================================================================


@app.route("/cart/clear", methods=["POST"])
def cart_clear():
    """
    Endpoint untuk menghapus semua item dari cart

    Fungsi ini:
    1. Mengosongkan cart (set ke empty list)
    2. Reset cart count ke 0
    3. Mark session as modified
    4. Return success response

    Use Cases:
        - User klik tombol "Clear All" / "Hapus Semua"
        - Memulai transaksi baru setelah pembayaran
        - Cancel order dan start over

    Request:
        POST /cart/clear
        (No body required)

    Response (JSON):
        {
            "success": true
        }

    Note:
        - Tidak ada validasi atau error handling khusus
        - Operation selalu berhasil (idempotent)
        - Memanggil endpoint ini multiple times aman
    """

    # Kosongkan cart dengan set ke empty list
    # Ini akan menghapus semua items yang ada
    # Previous cart data akan lost (tidak bisa undo)
    session["jumlahcart"] = []

    # Reset cart count badge ke 0
    # Ini untuk update icon cart counter di navbar
    session["cart_count"] = 0

    # CRITICAL: Mark session as modified
    # Tanpa ini, cart tidak akan ter-clear di server
    session.modified = True

    # Return success response
    # Frontend akan:
    # 1. Clear display cart items
    # 2. Reset all totals to "-" or 0
    # 3. Reset form inputs
    # 4. Update badge counter
    # 5. Show success message (optional)
    return jsonify({"success": True})


# ========================================================================
# API ENDPOINT - DOWNLOAD STRUK PDF
# ========================================================================


@app.route("/generate_struk", methods=["POST"])
def generate_struk():
    """
    Generate dan download PDF struk pembayaran

    Endpoint ini melakukan:
    1. Validasi cart dan input pembeli
    2. Generate PDF dengan ReportLab di memory (BytesIO)
    3. Return PDF binary untuk di-download browser

    Features:
        - Professional PDF layout dengan logo
        - Auto page-break untuk long receipts
        - Unique filename dengan timestamp
        - Support JSON dan Form data
        - Compatible dengan semua browser & download managers

    Request Methods:
        JSON (AJAX):
            POST /generate_struk
            Content-Type: application/json
            Body: {"nama": "John", "cash": 100000}

        Form Data (Traditional):
            POST /generate_struk
            Content-Type: application/x-www-form-urlencoded
            Body: nama=John&cash=100000

    Response:
        Success: PDF Binary (application/pdf) dengan status 200
        Error: JSON {"error": "..."} dengan status 400/500
    """

    try:
        # ============================================================
        # STEP 1: VALIDASI CART TIDAK KOSONG
        # ============================================================

        # Ambil cart dari session
        # Default empty list jika session baru atau cart sudah di-clear
        cart = session.get("jumlahcart", [])

        # Validasi: cart minimal harus punya 1 item
        # Prevent generate struk untuk transaksi kosong
        if not cart:
            # Return JSON error dengan status 400 Bad Request
            return jsonify({"error": "Keranjang kosong"}), 400

        # ============================================================
        # STEP 2: SUPPORT MULTIPLE INPUT FORMATS
        # ============================================================

        # Flask bisa terima data dalam 2 format:
        # 1. JSON - untuk AJAX/fetch requests (modern)
        # 2. Form Data - untuk traditional form submission (legacy)

        if request.is_json:
            # Request dengan Content-Type: application/json
            # Parse JSON body ke Python dict
            data = request.get_json()
        else:
            # Request dengan Content-Type: application/x-www-form-urlencoded
            # atau multipart/form-data
            # Convert ImmutableMultiDict ke regular dict
            data = request.form.to_dict()

        # ============================================================
        # STEP 3: VALIDASI & EXTRACT INPUT PEMBELI
        # ============================================================

        # Extract nama pembeli
        # .get("nama", "") = return empty string jika key tidak ada
        # .strip() = remove leading/trailing whitespace
        # Contoh: "  John Doe  " → "John Doe"
        nama = data.get("nama", "").strip()

        # Validasi & convert cash ke integer
        try:
            # int() convert string ke integer
            # Rupiah tidak ada decimal, jadi int sudah cukup
            cash = int(data.get("cash", 0))

        except (ValueError, TypeError):
            # ValueError: input bukan angka (contoh: "abc", "12.5")
            # TypeError: input None atau type yang tidak compatible

            # Return user-friendly error message
            return jsonify({"error": "Jumlah uang tidak valid"}), 400

        # ============================================================
        # STEP 4: HITUNG TOTAL & KEMBALIAN
        # ============================================================

        # Hitung subtotal dari semua items
        # Generator expression: (expr for item in list)
        # Lebih memory efficient daripada list comprehension
        subtotal = sum(item["price"] * item["qty"] for item in cart)

        # Hitung diskon, PPN, dan total akhir
        # Menggunakan helper function yang sudah kita buat sebelumnya
        # Return tuple: (diskon, ppn, total)
        diskon, ppn, total = hitung_total(subtotal)

        # Hitung kembalian
        # Simple: uang yang dibayar - total yang harus dibayar
        kembalian = cash - total

        # Validasi: uang harus cukup
        # Jika cash < total, return error
        if cash < total:
            return jsonify({"error": "Uang tidak cukup"}), 400

        # ============================================================
        # STEP 5: INISIALISASI PDF - CREATE BUFFER
        # ============================================================

        # BytesIO = in-memory binary stream (file-like object)
        # Keuntungan menggunakan BytesIO vs file di disk:
        # 1. Faster - no disk I/O overhead
        # 2. Cleaner - no temporary file cleanup needed
        # 3. Secure - file tidak tersimpan di server
        # 4. Scalable - bisa handle concurrent requests tanpa file conflicts
        buffer = io.BytesIO()

        # Create PDF Canvas object
        # Canvas = drawing surface untuk create PDF
        # pagesize=A4 = standar internasional (595 × 842 points)
        # 1 point = 1/72 inch
        pdf = canvas.Canvas(buffer, pagesize=A4)

        # ============================================================
        # STEP 6: PDF HEADER - TITLE
        # ============================================================

        # Set font untuk title
        # Helvetica-Bold = built-in font di ReportLab (tidak perlu install)
        # Size 16 = large untuk title
        pdf.setFont("Helvetica-Bold", 16)

        # Draw centered text
        # Coordinate system: (0,0) = bottom-left corner
        # X=300 ≈ center (A4 width = 595 points)
        # Y=725 = near top of page
        pdf.drawCentredString(300, 725, "Restoran Kelompok 4")

        # ============================================================
        # STEP 7: PDF HEADER - LOGO
        # ============================================================

        try:
            # ImageReader = ReportLab class untuk load dan process images
            # Support: PNG, JPG, GIF
            logo = ImageReader("static/img/logo.png")

            # Draw image pada canvas
            # Parameters:
            # - image: ImageReader object
            # - x: (595/2 - 40) = center X position minus half of image width
            # - y: 750 = near top, above title
            # - width, height: 80x80 pixels
            # - preserveAspectRatio: True = maintain original ratio (no distortion)
            pdf.drawImage(
                logo,
                (595 / 2) - 40,  # X coordinate
                750,  # Y coordinate
                width=80,
                height=80,
                preserveAspectRatio=True,
            )

        except Exception as e:
            # Exception bisa terjadi jika:
            # - File tidak ditemukan
            # - File corrupt
            # - Format tidak supported

            # Log warning tapi TIDAK stop execution
            # PDF generation tetap lanjut tanpa logo
            # This is graceful degradation
            app.logger.warning(f"Logo not found: {str(e)}")

        # ============================================================
        # STEP 8: PDF HEADER - INFO RESTORAN
        # ============================================================

        # Change font ke normal (non-bold) dengan size lebih kecil
        pdf.setFont("Helvetica", 10)

        # Alamat restoran - centered, multi-line text dalam 1 string
        pdf.drawCentredString(
            300,  # X: center
            695,  # Y: below title
            "Cikarang Square, Jl. Cibarusah Raya No.168, Pasirsari, "
            "Cikarang Sel, Kab.Bekasi, Jawa Barat 17550",
        )

        # Tanggal dan waktu transaksi
        # datetime.now() = current date/time
        # strftime() = format datetime ke string
        # Format: DD-MM-YYYY HH:MM (24-hour format)
        pdf.drawCentredString(
            290,  # X: slightly left of center
            682,  # Y: below address
            f"Tanggal: {datetime.datetime.now().strftime('%d-%m-%Y %H:%M')}",
        )

        # Horizontal line sebagai separator
        # line(x1, y1, x2, y2) draws line from point 1 to point 2
        # From left margin (40) to right margin (550)
        pdf.line(40, 670, 550, 670)

        # ============================================================
        # STEP 9: PDF BODY - NAMA PEMBELI
        # ============================================================

        # Variable y = vertical cursor position
        # Kita track y position untuk:
        # 1. Control spacing antar lines
        # 2. Detect kapan perlu page break
        # 3. Ensure text tidak overlap
        y = 650  # Start position below header separator

        # Bold font untuk labels
        pdf.setFont("Helvetica-Bold", 12)

        # Draw text left-aligned
        # drawString (bukan drawCentredString) = left aligned dari X position
        pdf.drawString(40, y, f"Nama Pembeli: {nama}")

        # Move cursor down
        # Y coordinate decreases saat move down (bottom-up coordinate system)
        y -= 25  # Spacing 25 points untuk section

        # ============================================================
        # STEP 10: PDF BODY - DAFTAR PEMBELIAN
        # ============================================================

        # Section header
        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawString(40, y, "Daftar Pembelian:")
        y -= 20  # Smaller spacing untuk sub-section

        # Change to normal font untuk list items
        pdf.setFont("Helvetica", 11)

        # Loop setiap item di cart
        for item in cart:
            # Left column: Item name dan quantity
            # Format: "Nasi Goreng  x2"
            # 2 spaces sebelum 'x' untuk readability
            pdf.drawString(40, y, f"{item['nama']}  x{item['qty']}")

            # Right column: Price per item × quantity
            # drawRightString = text right-aligned dari X position
            # X=550 = right margin
            # :, = thousand separator formatting
            # Contoh: 25000 → "25,000"
            pdf.drawRightString(550, y, f"Rp {item['price'] * item['qty']:,}")

            # Move to next line
            y -= 20

            # CRITICAL: Page overflow handling
            # Check if approaching bottom of page
            # 100 points = safety margin from bottom
            if y < 100:
                # Finish current page dan start new page
                # showPage() = commit current page, start fresh page
                pdf.showPage()

                # Reset cursor ke top of new page
                # 750 ≈ near top dengan margin
                y = 750

                # Optional: Re-draw headers di new page
                # (tidak implemented here, tapi bisa ditambahkan)

        # ============================================================
        # STEP 11: PDF BODY - SEPARATOR LINE
        # ============================================================

        # Horizontal line sebelum total section
        pdf.line(40, y, 550, y)
        y -= 25  # Space setelah line

        # ============================================================
        # STEP 12: PDF BODY - RINCIAN TOTAL
        # ============================================================

        # Bold font untuk total section
        pdf.setFont("Helvetica-Bold", 12)

        # ===== Subtotal =====
        pdf.drawString(40, y, "Subtotal:")
        pdf.drawRightString(550, y, f"Rp {subtotal:,}")
        y -= 20

        # ===== Diskon 10% =====
        pdf.drawString(40, y, "Diskon 10%:")
        pdf.drawRightString(550, y, f"Rp {diskon:,}")
        y -= 20

        # ===== PPN 10% =====
        # IMPORTANT: PPN dihitung dari DPP (setelah diskon)
        # Bukan dari subtotal!
        pdf.drawString(40, y, "PPN 10%:")
        pdf.drawRightString(550, y, f"Rp {ppn:,}")
        y -= 20

        # ===== Total yang harus dibayar =====
        pdf.drawString(40, y, "Total:")
        pdf.drawRightString(550, y, f"Rp {total:,}")
        y -= 20

        # ===== Uang yang dibayar =====
        pdf.drawString(40, y, "Uang Bayar:")
        pdf.drawRightString(550, y, f"Rp {cash:,}")
        y -= 20

        # ===== Kembalian =====
        pdf.drawString(40, y, "Kembalian:")
        pdf.drawRightString(550, y, f"Rp {kembalian:,}")
        y -= 50  # Larger spacing sebelum footer

        # ============================================================
        # STEP 13: PDF FOOTER
        # ============================================================

        # Decorative line menggunakan underscore characters
        # "_" * 76 = string dengan 76 underscore characters
        # Creates visual separator line
        pdf.drawString(40, y, "_" * 76)
        y -= 20

        # Thank you message
        # Not centered untuk simplicity, tapi positioned nicely
        pdf.drawString(200, y, "Terimakasih sudah berkunjung.")

        # ============================================================
        # STEP 14: FINALIZE PDF
        # ============================================================

        # CRITICAL STEP 1: Commit current page
        # showPage() finalize current page dan add ke document
        # Tanpa ini, halaman terakhir tidak akan muncul di PDF!
        pdf.showPage()

        # CRITICAL STEP 2: Save PDF
        # pdf.save() compile all drawing commands dan write ke buffer
        # Ini menghasilkan actual PDF binary data
        pdf.save()

        # CRITICAL STEP 3: Reset buffer pointer
        # buffer.seek(0) move read pointer ke beginning of buffer
        # Tanpa ini, subsequent read akan start dari end → 0 bytes!
        # This is the most common bug dalam PDF generation
        buffer.seek(0)

        # Debug: Print PDF size untuk verify generation successful
        # getbuffer().nbytes = total bytes in buffer
        # Typical receipt: 5-20 KB tergantung jumlah items
        print("PDF SIZE:", buffer.getbuffer().nbytes)

        # ============================================================
        # STEP 15: GENERATE FILENAME
        # ============================================================

        # Create unique filename dengan timestamp
        # Format: struk-DD-MM-YYYY-HHMMSS.pdf
        # Contoh: struk-27-11-2024-143052.pdf
        #
        # Benefits:
        # - Unique: no filename conflicts
        # - Sortable: chronological order
        # - Descriptive: user knows when it was generated
        tanggal = datetime.datetime.now().strftime("%d-%m-%Y-%H%M%S")
        fileDownload = f"struk-{tanggal}.pdf"

        # ============================================================
        # STEP 16: CREATE RESPONSE WITH HEADERS
        # ============================================================

        # send_file() = Flask function untuk send file responses
        # Parameters:
        # - buffer: file-like object (BytesIO)
        # - mimetype: Content-Type header
        # - as_attachment: True = trigger download, False = open in browser
        # - download_name: suggested filename untuk browser
        response = send_file(
            buffer,
            mimetype="application/pdf",  # Tell browser this is PDF
            as_attachment=True,  # Trigger download dialog
            download_name=fileDownload,  # Suggested filename
        )

        # ============================================================
        # STEP 17: ADD ADDITIONAL HEADERS
        # ============================================================

        # These headers improve compatibility dengan:
        # - All browsers (Chrome, Firefox, Safari, Edge)
        # - Download managers (IDM, Free Download Manager)
        # - Mobile browsers
        # - Corporate proxies/firewalls

        # Cache-Control: Prevent browser dari caching PDF
        # no-cache = always revalidate
        # no-store = jangan simpan di disk
        # must-revalidate = check with server before using cache
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"

        # Pragma: Legacy HTTP/1.0 cache control (for old browsers)
        response.headers["Pragma"] = "no-cache"

        # Expires: Set expiration date to past (immediate expiry)
        response.headers["Expires"] = "0"

        # Content-Disposition: Tell browser how to handle file
        # attachment = download file (bukan display inline)
        # filename = suggested filename dengan quotes untuk special chars support
        response.headers["Content-Disposition"] = (
            f'attachment; filename="{fileDownload}"'
        )

        # Content-Length: Size of response body in bytes
        # Enables:
        # - Download progress bar
        # - Resume capability (untuk download managers)
        # - Connection keep-alive optimization
        response.headers["Content-Length"] = str(buffer.getbuffer().nbytes)

        # ============================================================
        # STEP 18: RETURN RESPONSE
        # ============================================================

        # Return response object
        # Flask akan:
        # 1. Set status code ke 200 OK (default)
        # 2. Add all headers yang sudah kita set
        # 3. Stream PDF binary ke client
        # 4. Close connection setelah selesai
        return response

    # ============================================================
    # EXCEPTION HANDLING
    # ============================================================

    except Exception as e:
        # Catch-all untuk unexpected errors
        # Possible errors:
        # - ReportLab errors (font issues, drawing errors)
        # - Memory errors (buffer overflow)
        # - Any runtime exceptions

        # Print error ke console untuk debugging
        # Di production, ini akan masuk ke log file
        print("ERROR:", e)

        # Return response based on request type
        # Smart error handling untuk different contexts

        if request.is_json:
            # AJAX/fetch request expect JSON response
            # Return JSON dengan error message dan status 500
            # str(e) convert exception ke string message
            return jsonify({"error": str(e)}), 500
        else:
            # Traditional form submission expect HTML
            # Return simple HTML error page
            # User sees error message di browser
            return f"<html><body><h1>Error: {str(e)}</h1></body></html>", 500


# ========================================================================
# API ENDPOINT - GET CART FROM SESSION
# ========================================================================


@app.route("/cart/get", methods=["GET"])
def cart_get():
    """
    Retrieve current cart from session

    Endpoint ini mengatasi masalah:
    "Cart hilang setelah page refresh"

    Problem:
        - JavaScript variables = client-side memory
        - Page refresh → JavaScript reset
        - Cart data hilang dari frontend

    Solution:
        - Cart tersimpan di server session
        - Page load → JavaScript call /cart/get
        - Backend return cart dari session
        - Frontend restore display

    Use Cases:
        1. Page refresh - restore cart state
        2. Initial page load - check existing cart
        3. After session restore - sync frontend-backend

    Request:
        GET /cart/get
        (No parameters required)

    Response (JSON):
        Success (200):
        {
            "cart": [...],        # List of items dengan qty, price, dll
            "count": 5,           # Total quantity untuk badge counter
            "subtotal": 100000,   # Total sebelum diskon
            "diskon": 10000,      # Diskon amount
            "ppn": 9000,          # Pajak amount
            "total": 99000        # Final total
        }

        Error (500):
        {
            "error": "Internal server error"
        }
    """

    try:
        # ============================================================
        # STEP 1: LOAD CART FROM SESSION
        # ============================================================

        # Ambil cart dari server session
        # session = Flask's secure cookie-based session
        # Default empty list jika:
        # - Session baru (first visit)
        # - Cart sudah di-clear
        # - Session expired
        cart = session.get("jumlahcart", [])

        # ============================================================
        # STEP 2: CALCULATE TOTALS
        # ============================================================

        # Hitung semua totals even jika cart kosong
        # Jika cart = [], calculate_totals akan return (0, 0, 0, 0)
        # Ini lebih consistent daripada conditional calculation
        subtotal, diskon, ppn, total = calculate_totals(cart)

        # ============================================================
        # STEP 3: RETURN JSON RESPONSE
        # ============================================================

        # Return JSON dengan format yang sama seperti /cart/update
        # API consistency = easier frontend implementation
        return jsonify(
            {
                "cart": cart,  # List semua items
                "count": sum(i["qty"] for i in cart),  # Total qty untuk badge
                "subtotal": subtotal,  # Total before discount
                "diskon": diskon,  # Discount amount
                "ppn": ppn,  # Tax amount
                "total": total,  # Final total
            }
        )

    # ============================================================
    # EXCEPTION HANDLING
    # ============================================================

    except Exception as e:
        # Catch unexpected errors
        # Possible causes:
        # - Session corruption
        # - Calculate error
        # - JSON serialization error

        # Log error untuk debugging
        # app.logger.error() write ke Flask log file
        # Includes timestamp, severity level, message
        app.logger.error(f"Error in cart_get: {str(e)}")

        # Return generic error response
        # Status 500 = Internal Server Error
        # Frontend akan display error message ke user
        return jsonify({"error": "Internal server error"}), 500


if __name__ == "__main__":
    app.run(debug=True)
