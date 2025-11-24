// ==========================================================

let cart = {};

function updateCartDisplay(serverCart) {
  cart = {};
  serverCart.forEach((item) => {
    cart[item.id] = item;
  });

  renderCart();
}

// ADD TO CART button
document.addEventListener("click", (e) => {
  if (e.target.classList.contains("btn-cart")) {
    e.preventDefault();
    const id = e.target.dataset.id;
    updateCart("add", id);
  }
});

// PLUS / MINUS / REMOVE
document.addEventListener("click", (e) => {
  if (e.target.classList.contains("btn-plus")) {
    updateCart("plus", e.target.dataset.id);
  }
  if (e.target.classList.contains("btn-minus")) {
    updateCart("minus", e.target.dataset.id);
  }
  if (e.target.classList.contains("btn-remove")) {
    updateCart("remove", e.target.dataset.id);
  }
});

// CALL API
function updateCart(action, id) {
  fetch("/cart/update", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action: action, id: id }),
  })
    .then((res) => res.json())
    .then((data) => {
      updateCartDisplay(data.cart);
      document.getElementById("jumlahcart").innerHTML = `<span>${data.count}</span>`;
    });
}

function renderCart() {
  const wrapper = document.getElementById("wrapper");
  wrapper.innerHTML = "";

  Object.values(cart).forEach((item) => {
    wrapper.innerHTML += `
      <div class="row d-flex justify-content-between align-items-center wrapper-row">

        <div class="col-lg-2">
          <div class="cards d-flex justify-content-between align-items-center">
            
            <img src="${item.img}" class="img-thumbnail" />
          </div>
        </div>

        <div class="col-lg-4">
          <div class="card d-flex justify-content-center align-items-center card-item">
            <h6 class="mb-2">${item.nama}</h6>
            <h6>Rp ${item.subtotal.toLocaleString("id-ID")}</h6>
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
      </div>`;
  });
}

// rincian bayyar
document.addEventListener("click", (e) => {
  if (e.target.classList.contains("btn-proses")) {
    prosesPembayaran();
  }
});

function prosesPembayaran() {
  const nama = document.getElementById("inputNamaPembeli").value;
  const cash = document.getElementById("inputCash").value;

  fetch("/checkout", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ nama: nama, cash: cash }),
  })
    .then((res) => res.json())
    .then((data) => {
      document.getElementById("Subtotal").innerText = "Rp " + data.subtotal.toLocaleString("id-ID");
      document.getElementById("ppn").innerText = "Rp " + data.ppn.toLocaleString("id-ID");
      document.getElementById("diskon").innerText = "Rp " + data.diskon.toLocaleString("id-ID");
      document.getElementById("total").innerText = "Rp " + data.total.toLocaleString("id-ID");
      document.getElementById("uangBayar").innerText = "Rp " + data.cash.toLocaleString("id-ID");
      document.getElementById("kembalian").innerText = "Rp " + data.kembalian.toLocaleString("id-ID");
    });
}
// itung total otomatis
function updateCart(action, id) {
  fetch("/cart/update", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action: action, id: id }),
  })
    .then((res) => res.json())
    .then((data) => {
      updateCartDisplay(data.cart);
      document.getElementById("jumlahcart").innerHTML = `<span>${data.count}</span>`;

      // UPDATE subtotal otomatis!!
      document.getElementById("testTotal").innerText = "Rp " + data.subtotal.toLocaleString("id-ID");
    });
}

// clear
document.querySelector(".btn-clear").addEventListener("click", () => {
  fetch("/cart/clear", {
    method: "POST",
  })
    .then((res) => res.json())
    .then((data) => {
      if (data.success) {
        document.getElementById("wrapper").innerHTML = "";
        document.getElementById("jumlahcart").innerHTML = "<span>0</span>";
        document.getElementById("Subtotal").textContent = "-";
        document.getElementById("ppn").textContent = "-";
        document.getElementById("diskon").textContent = "0";
        document.getElementById("total").textContent = "-";
        document.getElementById("uangBayar").textContent = "-";
        document.getElementById("kembalian").textContent = "-";

        document.getElementById("inputNamaPembeli").value = "";
        document.getElementById("inputCash").value = "";
        document.getElementById("testTotal").innerText = "-";
      }
    });
});

// sturk

document.addEventListener("click", (e) => {
  if (e.target.classList.contains("btn-struk")) {
    const nama = document.getElementById("inputNamaPembeli").value;
    const cash = document.getElementById("inputCash").value;

    fetch("/download_struk", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ nama: nama, cash: cash }),
    });
  }
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


