let cart = {};
let isProcessing = false; // Prevent double-click

// ===================================== HELPER FUNCTIONS
function showError(message) {
  // Bisa diganti dengan toast notification yang lebih bagus
  alert(message);
}

function showSuccess(message) {
  alert(message);
}

function formatRupiah(angka) {
  return angka.toLocaleString("id-ID");
}

function validateNama(nama) {
  if (!nama || nama.trim() === "") {
    showError("Nama pembeli tidak boleh kosong!");
    return false;
  }
  if (nama.trim().length < 3) {
    showError("Nama pembeli minimal 3 karakter!");
    return false;
  }
  return true;
}

function validateCash(cash) {
  if (!cash || isNaN(cash) || cash <= 0) {
    showError("Jumlah uang tidak valid!");
    return false;
  }
  return true;
}

function disableButtons(disable) {
  const buttons = document.querySelectorAll(".btn-cart, .btn-plus, .btn-minus, .btn-remove, .btn-proses, .btn-clear, .btn-struk");
  buttons.forEach((btn) => {
    btn.disabled = disable;
  });
}

// ===================================== UPDATE CART DISPLAY
function updateCartDisplay(serverCart) {
  cart = {};
  serverCart.forEach((item) => {
    cart[item.id] = item;
  });
  renderCart();
}

// ===================================== RENDER CART
function renderCart() {
  const wrapper = document.getElementById("wrapper");

  if (!wrapper) {
    console.error("Element #wrapper tidak ditemukan");
    return;
  }

  if (Object.keys(cart).length === 0) {
    wrapper.innerHTML = '<div class="text-center py-5"><p class="text-muted">Keranjang kosong</p></div>';
    return;
  }

  wrapper.innerHTML = "";

  Object.values(cart).forEach((item) => {
    wrapper.innerHTML += `
      <div class="row d-flex justify-content-between align-items-center wrapper-row">
        <div class="col-lg-2">
          <div class="cards d-flex justify-content-between align-items-center">
            <img src="${item.img}" class="img-thumbnail" alt="${item.nama}" />
          </div>
        </div>

        <div class="col-lg-4">
          <div class="card d-flex justify-content-center align-items-center card-item">
            <h6 class="mb-2">${item.nama}</h6>
            <h6>Rp ${formatRupiah(item.subtotal)}</h6>
          </div>
        </div>

        <div class="col-lg-3">
          <div class="card card-btngrup border-0">
            <div class="btn-group border-0 d-flex justify-content-between align-items-center">
              <button class="btn btn-plus" data-id="${item.id}">+</button>
              <h6 class="mx-2">${item.qty}</h6>
              <button class="btn btn-minus" data-id="${item.id}">-</button>
            </div>
          </div>
        </div>

        <div class="col-lg-2">
          <button class="btn btn-danger btn-sm btn-remove" data-id="${item.id}">
            <i class="fas fa-trash"></i> Hapus
          </button>
        </div>
      </div>`;
  });
}

// ===================================== UPDATE CART (UNIFIED FUNCTION)
function updateCart(action, id) {
  if (isProcessing) return;

  isProcessing = true;
  disableButtons(true);

  fetch("/cart/update", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action: action, id: id }),
  })
    .then((res) => {
      if (!res.ok) {
        return res.json().then((err) => {
          throw new Error(err.error || "Terjadi kesalahan");
        });
      }
      return res.json();
    })
    .then((data) => {
      // Update cart display
      updateCartDisplay(data.cart);

      // Update cart count badge
      const cartBadge = document.getElementById("jumlahcart");
      if (cartBadge) {
        cartBadge.innerHTML = `<span>${data.count}</span>`;
      }

      // Update subtotal otomatis
      const testTotal = document.getElementById("testTotal");
      if (testTotal) {
        testTotal.innerText = data.count > 0 ? `Rp ${formatRupiah(data.subtotal)}` : "-";
      }

      // Reset form pembayaran jika cart kosong
      if (data.count === 0) {
        resetPaymentForm();
      }
    })
    .catch((error) => {
      console.error("Error updating cart:", error);
      showError(error.message || "Gagal mengupdate keranjang");
    })
    .finally(() => {
      isProcessing = false;
      disableButtons(false);
    });
}

// ===================================== EVENT LISTENERS

// ADD TO CART button
document.addEventListener("click", (e) => {
  if (e.target.classList.contains("btn-cart")) {
    e.preventDefault();
    const id = e.target.dataset.id;
    if (id) {
      updateCart("add", id);
    }
  }
});

// PLUS / MINUS / REMOVE
document.addEventListener("click", (e) => {
  if (e.target.classList.contains("btn-plus")) {
    const id = e.target.dataset.id;
    if (id) updateCart("plus", id);
  }

  if (e.target.classList.contains("btn-minus")) {
    const id = e.target.dataset.id;
    if (id) updateCart("minus", id);
  }

  if (e.target.classList.contains("btn-remove")) {
    const id = e.target.dataset.id;
    if (id && confirm("Hapus item ini dari keranjang?")) {
      updateCart("remove", id);
    }
  }
});

// ===================================== PROSES PEMBAYARAN
document.addEventListener("click", (e) => {
  if (e.target.classList.contains("btn-proses")) {
    e.preventDefault();
    prosesPembayaran();
  }
});

function prosesPembayaran() {
  if (isProcessing) return;

  const nama = document.getElementById("inputNamaPembeli")?.value.trim();
  const cashInput = document.getElementById("inputCash")?.value;
  const cash = parseInt(cashInput);

  // Validasi input
  if (!validateNama(nama)) return;
  if (!validateCash(cash)) return;

  // Cek apakah cart kosong
  if (Object.keys(cart).length === 0) {
    showError("Keranjang masih kosong!");
    return;
  }

  isProcessing = true;
  disableButtons(true);

  fetch("/checkout", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ nama: nama, cash: cash }),
  })
    .then((res) => {
      if (!res.ok) {
        return res.json().then((err) => {
          throw new Error(err.error || "Terjadi kesalahan");
        });
      }
      return res.json();
    })
    .then((data) => {
      // Update rincian pembayaran
      updateElement("Subtotal", `Rp ${formatRupiah(data.subtotal)}`);
      updateElement("ppn", `Rp ${formatRupiah(data.ppn)}`);
      updateElement("diskon", `Rp ${formatRupiah(data.diskon)}`);
      updateElement("total", `Rp ${formatRupiah(data.total)}`);
      updateElement("uangBayar", `Rp ${formatRupiah(data.cash)}`);
      updateElement("kembalian", `Rp ${formatRupiah(data.kembalian)}`);

      showSuccess("Pembayaran berhasil diproses!");
    })
    .catch((error) => {
      console.error("Error processing payment:", error);
      showError(error.message || "Gagal memproses pembayaran");
    })
    .finally(() => {
      isProcessing = false;
      disableButtons(false);
    });
}

function updateElement(id, value) {
  const element = document.getElementById(id);
  if (element) {
    element.innerText = value;
  }
}

// ===================================== CLEAR CART
function initClearButton() {
  const clearBtn = document.querySelector(".btn-clear");
  if (clearBtn) {
    clearBtn.addEventListener("click", clearCart);
  }
}

function clearCart() {
  if (!confirm("Hapus semua item di keranjang?")) return;

  if (isProcessing) return;

  isProcessing = true;
  disableButtons(true);

  fetch("/cart/clear", {
    method: "POST",
  })
    .then((res) => {
      if (!res.ok) {
        throw new Error("Gagal menghapus keranjang");
      }
      return res.json();
    })
    .then((data) => {
      if (data.success) {
        // Clear display
        const wrapper = document.getElementById("wrapper");
        if (wrapper) {
          wrapper.innerHTML = '<div class="text-center py-5"><p class="text-muted">Keranjang kosong</p></div>';
        }

        // Reset cart count
        const cartBadge = document.getElementById("jumlahcart");
        if (cartBadge) {
          cartBadge.innerHTML = "<span>0</span>";
        }

        // Reset totals
        updateElement("testTotal", "-");
        resetPaymentForm();

        // Clear local cart
        cart = {};

        showSuccess("Keranjang berhasil dikosongkan!");
      }
    })
    .catch((error) => {
      console.error("Error clearing cart:", error);
      showError(error.message || "Gagal menghapus keranjang");
    })
    .finally(() => {
      isProcessing = false;
      disableButtons(false);
    });
}

function resetPaymentForm() {
  // Reset payment summary
  updateElement("Subtotal", "-");
  updateElement("ppn", "-");
  updateElement("diskon", "-");
  updateElement("total", "-");
  updateElement("uangBayar", "-");
  updateElement("kembalian", "-");

  // Clear form inputs
  const namaInput = document.getElementById("inputNamaPembeli");
  const cashInput = document.getElementById("inputCash");

  if (namaInput) namaInput.value = "";
  if (cashInput) cashInput.value = "";
}

// ===================================== DOWNLOAD STRUK
document.addEventListener("click", (e) => {
  if (e.target.classList.contains("btn-struk")) {
    e.preventDefault();
    downloadStruk();
  }
});

function downloadStruk() {
  if (isProcessing) return;

  const nama = document.getElementById("inputNamaPembeli")?.value.trim();
  const cashInput = document.getElementById("inputCash")?.value;
  const cash = parseInt(cashInput);

  // Validasi input
  if (!validateNama(nama)) return;
  if (!validateCash(cash)) return;

  // Cek apakah sudah diproses pembayaran
  const totalElement = document.getElementById("total");
  if (!totalElement || totalElement.innerText === "-") {
    showError("Silakan proses pembayaran terlebih dahulu!");
    return;
  }

  isProcessing = true;
  disableButtons(true);

  // Generate filename SEBELUM request
  const today = new Date();
  const dateStr = today.toLocaleDateString("id-ID").split("/").reverse().join("-");
  const filename = `struk-${dateStr}.pdf`;

  // METODE BARU: Gunakan direct link download (compatible dengan IDM)
  const form = document.createElement("form");
  form.method = "POST";
  form.action = "/download_struk";
  form.style.display = "none";

  // Add CSRF token if you use it
  // const csrfInput = document.createElement('input');
  // csrfInput.name = 'csrf_token';
  // csrfInput.value = 'YOUR_CSRF_TOKEN';
  // form.appendChild(csrfInput);

  const namaInput = document.createElement("input");
  namaInput.name = "nama";
  namaInput.value = nama;
  form.appendChild(namaInput);

  const cashInputField = document.createElement("input");
  cashInputField.name = "cash";
  cashInputField.value = cash;
  form.appendChild(cashInputField);

  document.body.appendChild(form);
  form.submit();

  // Cleanup form setelah submit
  setTimeout(() => {
    document.body.removeChild(form);
    isProcessing = false;
    disableButtons(false);
    showSuccess("Struk sedang diunduh...");
  }, 500);
}

// ALTERNATIF: Jika tetap ingin pakai fetch (tapi kurang compatible dengan IDM)
function downloadStrukWithFetch() {
  if (isProcessing) return;

  const nama = document.getElementById("inputNamaPembeli")?.value.trim();
  const cashInput = document.getElementById("inputCash")?.value;
  const cash = parseInt(cashInput);

  if (!validateNama(nama)) return;
  if (!validateCash(cash)) return;

  const totalElement = document.getElementById("total");
  if (!totalElement || totalElement.innerText === "-") {
    showError("Silakan proses pembayaran terlebih dahulu!");
    return;
  }

  isProcessing = true;
  disableButtons(true);

  fetch("/download_struk", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ nama: nama, cash: cash }),
  })
    .then(async (res) => {
      const contentType = res.headers.get("content-type");

      if (contentType && contentType.includes("application/pdf")) {
        if (!res.ok) {
          throw new Error("Failed to generate PDF");
        }
        return res.blob();
      }

      if (contentType && contentType.includes("application/json")) {
        const errorData = await res.json();
        throw new Error(errorData.error || "Terjadi kesalahan");
      }

      throw new Error("Invalid response format");
    })
    .then((blob) => {
      if (!blob || blob.size === 0) {
        throw new Error("PDF kosong, silakan coba lagi");
      }

      console.log("PDF downloaded, size:", blob.size, "bytes");

      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.style.display = "none";
      a.href = url;

      const today = new Date();
      const dateStr = today.toLocaleDateString("id-ID").split("/").reverse().join("-");
      a.download = `struk-${dateStr}.pdf`;

      document.body.appendChild(a);

      // Trigger download
      a.click();

      // Cleanup SETELAH download selesai (penting untuk IDM)
      setTimeout(() => {
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
      }, 5000); // Increased dari 100ms ke 5000ms

      showSuccess("Struk berhasil diunduh!");
    })
    .catch((error) => {
      console.error("Error downloading struk:", error);
      showError(error.message || "Gagal mengunduh struk");
    })
    .finally(() => {
      isProcessing = false;
      disableButtons(false);
    });
}

// ===================================== LOAD CART FROM SERVER
function loadCartFromServer() {
  fetch("/cart/get", {
    method: "GET",
  })
    .then((res) => {
      if (!res.ok) {
        throw new Error("Gagal load cart");
      }
      return res.json();
    })
    .then((data) => {
      // Update cart display
      updateCartDisplay(data.cart);

      // Update cart count badge
      const cartBadge = document.getElementById("jumlahcart");
      if (cartBadge) {
        cartBadge.innerHTML = `<span>${data.count}</span>`;
      }

      // Update subtotal
      const testTotal = document.getElementById("testTotal");
      if (testTotal) {
        testTotal.innerText = data.count > 0 ? `Rp ${formatRupiah(data.subtotal)}` : "-";
      }

      console.log("Cart loaded from server:", data.count, "items");
    })
    .catch((error) => {
      console.error("Error loading cart:", error);
      // Jika error, tetap tampilkan cart kosong
      cart = {};
      renderCart();
    });
}

// ===================================== INITIALIZE
document.addEventListener("DOMContentLoaded", () => {
  initClearButton();
  loadCartFromServer(); // Load cart dari server saat page load
  console.log("Cart system initialized");
});
// ================================================Start tombol Navbar============================================================== //
// Mengambil elemen navbar dan semua tautan di dalamnya
const navbar = document.querySelector(".navbar");
const navLinks = navbar.querySelectorAll(".nav-link");

// Mendengarkan peristiwa scroll
window.addEventListener("scroll", () => {
  // Mendapatkan posisi scroll
  const scrollPosition = window.scrollY || document.documentElement.scrollTop || document.body.scrollTop;

  // Memperbarui kelas aktif pada tautan navigasi sesuai dengan posisi scroll
  navLinks.forEach((link) => {
    const section = document.querySelector(link.getAttribute("href"));
    const sectionTop = section.offsetTop - navbar.offsetHeight;
    const sectionHeight = section.offsetHeight;

    if (scrollPosition >= sectionTop && scrollPosition < sectionTop + sectionHeight) {
      link.classList.add("active");
    } else {
      link.classList.remove("active");
    }
  });
});

// Fungsi untuk menggulir ke bagian yang tepat saat tautan di navbar diklik
function scrollToSection(event, sectionId) {
  event.preventDefault();

  const section = document.querySelector(sectionId);
  const offsetTop = section.offsetTop - navbar.offsetHeight;

  window.scrollTo({
    top: offsetTop,
    behavior: "smooth",
  });

  // Memperbarui kelas aktif pada tautan navigasi setelah menggulir
  navLinks.forEach((link) => {
    if (link.getAttribute("href") === sectionId) {
      link.classList.add("active");
    } else {
      link.classList.remove("active");
    }
  });
}

// ================================================Start scroll reveals============================================================== //
ScrollReveal({
  reset: true,
  distance: "80px",
  duration: 2000,
  delay: 200,
});

ScrollReveal().reveal(".zhx", { origin: "bottom" });
ScrollReveal().reveal(".ftr", { origin: "bottom" });
ScrollReveal().reveal(".h1team", { origin: "top" });
ScrollReveal().reveal(".rfk", { origin: "left" });
ScrollReveal().reveal(".ndi", { origin: "bottom" });
ScrollReveal().reveal(".cia", { origin: "right" });
