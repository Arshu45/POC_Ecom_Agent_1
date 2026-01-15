// ============================================
// GLOBAL VARIABLES
// ============================================
let currentPage = 1;
let currentFilters = {};
let isChatLoading = false;

// ============================================
// CHAT FUNCTIONS
// ============================================

function toggleChat() {
  const chatSidebar = document.getElementById("chatSidebar");
  if (chatSidebar) {
    chatSidebar.classList.toggle("open");
    if (chatSidebar.classList.contains("open")) {
      setTimeout(() => {
        const chatInput = document.getElementById("chatInput");
        if (chatInput) chatInput.focus();
      }, 300);
    }
  }
}

async function sendChatMessage() {
  const chatInput = document.getElementById("chatInput");
  const chatMessages = document.getElementById("chatMessages");
  const followUpQuestions = document.getElementById("followUpQuestions");
  const chatSendBtn = document.getElementById("chatSendBtn");

  if (!chatInput || !chatMessages) return;

  const query = chatInput.value.trim();
  if (!query || isChatLoading) return;

  if (followUpQuestions) followUpQuestions.innerHTML = "";
  addChatMessage(query, "user");
  chatInput.value = "";

  isChatLoading = true;
  chatInput.disabled = true;
  if (chatSendBtn) chatSendBtn.disabled = true;

  const loadingId = addChatMessage("", "bot", true);

  try {
    const response = await fetch("/search", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ query: query }),
    });

    const data = await response.json();
    removeChatMessage(loadingId);

    if (data.success) {
      addChatMessage(data.response_text, "bot", false, false);

      if (data.products && data.products.length > 0) {
        addProductsToChat(data.products);
      }

      if (data.follow_up_questions && data.follow_up_questions.length > 0) {
        addFollowUpQuestions(data.follow_up_questions);
      }

      if (data.metadata) {
        const metaText = `Found ${data.metadata.total_results || 0} product(s)${
          data.metadata.in_stock_count
            ? `, ${data.metadata.in_stock_count} in stock`
            : ""
        }`;
        addChatMessage(metaText, "bot", false, true);
      }
    } else {
      addChatMessage(
        data.error_message || "Sorry, I encountered an error. Please try again.",
        "bot"
      );
    }
  } catch (error) {
    console.error("Chat error:", error);
    removeChatMessage(loadingId);
    addChatMessage(
      "Sorry, I encountered an error. Please check your connection and try again.",
      "bot"
    );
  } finally {
    isChatLoading = false;
    chatInput.disabled = false;
    if (chatSendBtn) chatSendBtn.disabled = false;
    chatInput.focus();
  }
}

function handleChatKeyPress(event) {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    sendChatMessage();
  }
}

function formatMessageText(text) {
  return text.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
}

function addChatMessage(text, type, isLoading = false, isMeta = false) {
  const chatMessages = document.getElementById("chatMessages");
  if (!chatMessages) return null;

  const messageDiv = document.createElement("div");
  const messageId = "msg-" + Date.now() + "-" + Math.random().toString(36).substr(2, 9);
  messageDiv.id = messageId;
  messageDiv.className = `chat-message ${type}-message`;

  if (isLoading) {
    messageDiv.innerHTML = `
      <div class="message-content">
        <div class="chat-loading">
          <div class="spinner-border spinner-border-sm" role="status"></div>
          <span>Searching products...</span>
        </div>
      </div>
    `;
  } else {
    const icon = type === "bot" ? '<i class="bi bi-robot"></i>' : "";
    const metaClass = isMeta ? "text-muted small" : "";
    const formattedText = type === "bot" ? formatMessageText(escapeHtml(text)) : escapeHtml(text);

    messageDiv.innerHTML = `
      <div class="message-content ${metaClass}">
        ${icon}
        <p>${formattedText}</p>
      </div>
    `;
  }

  chatMessages.appendChild(messageDiv);
  scrollChatToBottom();

  return messageId;
}

function removeChatMessage(messageId) {
  const message = document.getElementById(messageId);
  if (message) {
    message.remove();
  }
}

function addProductsToChat(products) {
  const chatMessages = document.getElementById("chatMessages");
  if (!chatMessages || !products || products.length === 0) return;

  const productsDiv = document.createElement("div");
  productsDiv.className = "chat-message bot-message";

  let productsHtml = '<div class="message-content"><p><strong>Recommended Products:</strong></p>';

  products.forEach((product) => {
    const featuresHtml =
      product.key_features && product.key_features.length > 0
        ? `<div class="chat-product-features">${product.key_features
            .map((f) => `<span class="badge bg-secondary">${escapeHtml(f)}</span>`)
            .join("")}</div>`
        : "";

    productsHtml += `
      <div class="chat-product-card" onclick="window.location.href='/product/${product.id}'">
        <div class="chat-product-title">${escapeHtml(product.title)}</div>
        <div class="chat-product-price">${escapeHtml(product.price)}</div>
        ${featuresHtml}
      </div>
    `;
  });

  productsHtml += "</div>";
  productsDiv.innerHTML = productsHtml;
  chatMessages.appendChild(productsDiv);
  scrollChatToBottom();
}

function addFollowUpQuestions(questions) {
  const followUpContainer = document.getElementById("followUpQuestions");
  if (!followUpContainer || !questions || questions.length === 0) return;

  followUpContainer.innerHTML = '<small class="text-muted d-block mb-2">Suggested questions:</small>';

  questions.forEach((question) => {
    const btn = document.createElement("button");
    btn.className = "follow-up-question-btn";
    btn.textContent = question;
    btn.onclick = () => {
      const chatInput = document.getElementById("chatInput");
      if (chatInput) {
        chatInput.value = question;
        sendChatMessage();
      }
    };
    followUpContainer.appendChild(btn);
  });
}

function scrollChatToBottom() {
  const chatMessages = document.getElementById("chatMessages");
  if (chatMessages) {
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

// ============================================
// PRODUCT LISTING FUNCTIONS
// ============================================

async function loadProducts(page = 1) {
  const loadingSpinner = document.getElementById("loadingSpinner");
  const productsGrid = document.getElementById("productsGrid");

  if (!productsGrid) return;

  if (loadingSpinner) loadingSpinner.classList.add("show");
  productsGrid.innerHTML = "";

  const params = new URLSearchParams({
    page: page,
    page_size: 12,
    ...currentFilters,
  });

  try {
    const response = await fetch(`/products?${params}`);
    const data = await response.json();

    const productCount = document.getElementById("productCount");
    if (productCount) {
      productCount.textContent = `Showing ${data.products.length} of ${data.total} products`;
    }

    if (data.products.length === 0) {
      productsGrid.innerHTML = `
        <div class="col-12">
          <div class="alert alert-info text-center">
            <i class="bi bi-inbox"></i> No products found. Try adjusting your filters.
          </div>
        </div>
      `;
    } else {
      data.products.forEach((product) => {
        const productCard = createProductCard(product);
        productsGrid.appendChild(productCard);
      });
    }

    updatePagination(data.total, data.page, data.page_size);
  } catch (error) {
    console.error("Error loading products:", error);
    productsGrid.innerHTML = `
      <div class="col-12">
        <div class="alert alert-danger">
          <i class="bi bi-exclamation-triangle"></i> Error loading products. Please try again.
        </div>
      </div>
    `;
  } finally {
    if (loadingSpinner) loadingSpinner.classList.remove("show");
  }
}

function createProductCard(product) {
  const col = document.createElement("div");
  col.className = "col-md-4 col-sm-6 mb-4";

  const discountBadge = product.discount_percent
    ? `<span class="discount-badge">${product.discount_percent}% OFF</span>`
    : "";

  const stockBadgeClass =
    {
      "In Stock": "bg-success",
      "Low Stock": "bg-warning",
      "Out of Stock": "bg-danger",
    }[product.stock_status] || "bg-secondary";

  const stockBadge = product.stock_status
    ? `<span class="badge ${stockBadgeClass} stock-badge">${product.stock_status}</span>`
    : "";

  const mrpDisplay =
    product.mrp && product.mrp > product.price
      ? `<span class="mrp">₹${product.mrp.toLocaleString()}</span>`
      : "";

  col.innerHTML = `
    <div class="card product-card h-100">
      <img src="${product.primary_image || "https://via.placeholder.com/400x400?text=No+Image"}" 
           class="card-img-top product-image" 
           alt="${product.title}"
           onerror="this.src='https://via.placeholder.com/400x400?text=No+Image'">
      <div class="card-body d-flex flex-column">
        <div class="mb-2">${stockBadge} ${discountBadge}</div>
        <h6 class="card-title">${product.title}</h6>
        <p class="text-muted small mb-2">
          <i class="bi bi-tag"></i> ${product.brand || "Unknown Brand"}
        </p>
        <div class="mt-auto">
          <div class="price-tag">
            ₹${product.price.toLocaleString()} ${mrpDisplay}
          </div>
          <a href="/product/${product.product_id}" class="btn btn-primary btn-sm w-100 mt-2">
            <i class="bi bi-eye"></i> View Details
          </a>
        </div>
      </div>
    </div>
  `;

  return col;
}

function updatePagination(total, page, pageSize) {
  const pagination = document.getElementById("pagination");
  if (!pagination) return;

  const totalPages = Math.ceil(total / pageSize);

  if (totalPages <= 1) {
    pagination.innerHTML = "";
    return;
  }

  let html = "";

  html += `
    <li class="page-item ${page === 1 ? "disabled" : ""}">
      <a class="page-link" href="#" data-page="${page - 1}">Previous</a>
    </li>
  `;

  for (let i = 1; i <= totalPages; i++) {
    if (i === 1 || i === totalPages || (i >= page - 2 && i <= page + 2)) {
      html += `
        <li class="page-item ${i === page ? "active" : ""}">
          <a class="page-link" href="#" data-page="${i}">${i}</a>
        </li>
      `;
    } else if (i === page - 3 || i === page + 3) {
      html += `<li class="page-item disabled"><span class="page-link">...</span></li>`;
    }
  }

  html += `
    <li class="page-item ${page === totalPages ? "disabled" : ""}">
      <a class="page-link" href="#" data-page="${page + 1}">Next</a>
    </li>
  `;

  pagination.innerHTML = html;

  pagination.querySelectorAll('a.page-link').forEach(link => {
    link.addEventListener('click', function(e) {
      e.preventDefault();
      const pageNum = parseInt(this.getAttribute('data-page'));
      if (pageNum && pageNum > 0) {
        loadProducts(pageNum);
      }
    });
  });
}

function applyFilters() {
  currentFilters = {};

  const brand = document.getElementById("filterBrand");
  if (brand && brand.value.trim()) currentFilters.brand = brand.value.trim();

  const minPrice = document.getElementById("minPrice");
  if (minPrice && minPrice.value) currentFilters.min_price = parseFloat(minPrice.value);

  const maxPrice = document.getElementById("maxPrice");
  if (maxPrice && maxPrice.value) currentFilters.max_price = parseFloat(maxPrice.value);

  const stock = document.getElementById("filterStock");
  if (stock && stock.value) currentFilters.stock_status = stock.value;

  const category = document.getElementById("filterCategory");
  if (category && category.value) currentFilters.category_id = parseInt(category.value);

  const color = document.getElementById("filterColor");
  if (color && color.value.trim()) currentFilters.color = color.value.trim();

  const size = document.getElementById("filterSize");
  if (size && size.value.trim()) currentFilters.size = size.value.trim();

  const gender = document.getElementById("filterGender");
  if (gender && gender.value) currentFilters.gender = gender.value;

  const ageGroup = document.getElementById("filterAgeGroup");
  if (ageGroup && ageGroup.value.trim()) currentFilters.age_group = ageGroup.value.trim();

  const occasion = document.getElementById("filterOccasion");
  if (occasion && occasion.value) currentFilters.occasion = occasion.value;

  const sortBy = document.getElementById("sortBy");
  if (sortBy) {
    if (sortBy.value === "price_desc") {
      currentFilters.sort_by = "price";
      currentFilters.sort_order = "desc";
    } else if (sortBy.value === "price") {
      currentFilters.sort_by = "price";
      currentFilters.sort_order = "asc";
    } else if (sortBy.value === "title") {
      currentFilters.sort_by = "title";
      currentFilters.sort_order = "asc";
    }
  }

  currentPage = 1;
  loadProducts(1);
}

function clearFilters() {
  const filterIds = [
    "filterBrand", "minPrice", "maxPrice", "filterStock", "filterCategory",
    "filterColor", "filterSize", "filterGender", "filterAgeGroup", "filterOccasion"
  ];

  filterIds.forEach(id => {
    const element = document.getElementById(id);
    if (element) element.value = "";
  });

  const sortBy = document.getElementById("sortBy");
  if (sortBy) sortBy.value = "product_id";

  currentFilters = {};
  currentPage = 1;
  loadProducts(1);
}

// ============================================
// PRODUCT DETAIL PAGE
// ============================================

async function loadProductDetails(productId) {
  const loadingSpinner = document.getElementById("loadingSpinner");
  const productDetails = document.getElementById("productDetails");
  const errorMessage = document.getElementById("errorMessage");

  try {
    const response = await fetch(`/products/${productId}`);

    if (!response.ok) {
      throw new Error("Product not found");
    }

    const product = await response.json();

    const productTitle = document.getElementById("productTitle");
    const productBrand = document.getElementById("productBrand");
    const productType = document.getElementById("productType");

    if (productTitle) productTitle.textContent = product.title;
    if (productBrand) productBrand.textContent = product.brand || "Unknown Brand";
    if (productType) productType.textContent = product.product_type || "N/A";

    const stockBadge = document.getElementById("stockBadge");
    if (stockBadge) {
      const stockClass = {
        "In Stock": "bg-success",
        "Low Stock": "bg-warning",
        "Out of Stock": "bg-danger",
      }[product.stock_status] || "bg-secondary";
      stockBadge.className = `badge ${stockClass}`;
      stockBadge.textContent = product.stock_status || "Unknown";
    }

    const priceDisplay = document.getElementById("priceDisplay");
    if (priceDisplay) priceDisplay.textContent = `₹${product.price.toLocaleString()}`;

    const mrpDisplay = document.getElementById("mrpDisplay");
    if (mrpDisplay) {
      if (product.mrp && product.mrp > product.price) {
        mrpDisplay.textContent = `MRP: ₹${product.mrp.toLocaleString()}`;
        mrpDisplay.style.display = "block";
      } else {
        mrpDisplay.style.display = "none";
      }
    }

    const discountBadge = document.getElementById("discountBadge");
    if (discountBadge) {
      if (product.discount_percent) {
        discountBadge.innerHTML = `<span class="badge bg-danger">${product.discount_percent}% OFF</span>`;
      } else {
        discountBadge.innerHTML = "";
      }
    }

    const mainImage = document.getElementById("mainImage");
    const thumbnailContainer = document.getElementById("thumbnailContainer");

    if (product.images && product.images.length > 0) {
      if (mainImage) {
        mainImage.src = product.images[0].image_url;
        mainImage.alt = product.title;
      }

      if (thumbnailContainer) {
        product.images.forEach((image, index) => {
          const thumbnail = document.createElement("img");
          thumbnail.src = image.image_url;
          thumbnail.className = "product-thumbnail" + (index === 0 ? " active" : "");
          thumbnail.onclick = () => {
            if (mainImage) mainImage.src = image.image_url;
            document.querySelectorAll(".product-thumbnail").forEach((t) => t.classList.remove("active"));
            thumbnail.classList.add("active");
          };
          thumbnail.onerror = function () {
            this.src = "https://via.placeholder.com/100x100?text=Image";
          };
          thumbnailContainer.appendChild(thumbnail);
        });
      }
    } else {
      if (mainImage) mainImage.src = "https://via.placeholder.com/500x500?text=No+Image";
    }

    const attributesTable = document.getElementById("attributesTable");
    if (attributesTable) {
      if (product.attributes && product.attributes.length > 0) {
        product.attributes.forEach((attr) => {
          const row = document.createElement("tr");
          row.innerHTML = `
            <td><strong>${formatAttributeName(attr.attribute_name)}</strong></td>
            <td>${attr.attribute_value || "N/A"}</td>
          `;
          attributesTable.appendChild(row);
        });
      } else {
        attributesTable.innerHTML = '<tr><td colspan="2" class="text-muted">No attributes available</td></tr>';
      }
    }

    const addToCartBtn = document.getElementById("addToCartBtn");
    if (addToCartBtn) {
      if (product.stock_status === "Out of Stock") {
        addToCartBtn.disabled = true;
        addToCartBtn.textContent = "Out of Stock";
      }
    }

    if (loadingSpinner) loadingSpinner.style.display = "none";
    if (productDetails) productDetails.style.display = "block";
  } catch (error) {
    console.error("Error loading product:", error);
    if (loadingSpinner) loadingSpinner.style.display = "none";
    if (errorMessage) {
      errorMessage.style.display = "block";
      const errorText = document.getElementById("errorText");
      if (errorText) errorText.textContent = error.message || "Failed to load product details";
    }
  }
}

function formatAttributeName(name) {
  return name
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

// ============================================
// INITIALIZATION
// ============================================

document.addEventListener("DOMContentLoaded", function () {
  // Initialize chat
  const chatToggleBtn = document.getElementById("chatToggleBtn");
  const closeChatBtn = document.getElementById("closeChatBtn");
  const chatSendBtn = document.getElementById("chatSendBtn");
  const chatInput = document.getElementById("chatInput");

  if (chatToggleBtn) {
    chatToggleBtn.addEventListener("click", toggleChat);
  }

  if (closeChatBtn) {
    closeChatBtn.addEventListener("click", toggleChat);
  }

  if (chatSendBtn) {
    chatSendBtn.addEventListener("click", sendChatMessage);
  }

  if (chatInput) {
    chatInput.addEventListener("keypress", handleChatKeyPress);
  }

  // Initialize product listing page
  const productsGrid = document.getElementById("productsGrid");
  if (productsGrid) {
    loadProducts();
    
    const applyFiltersBtn = document.getElementById("applyFiltersBtn");
    const clearFiltersBtn = document.getElementById("clearFiltersBtn");
    
    if (applyFiltersBtn) {
      applyFiltersBtn.addEventListener("click", applyFilters);
    }
    
    if (clearFiltersBtn) {
      clearFiltersBtn.addEventListener("click", clearFilters);
    }
  }

  // Initialize product detail page
  const productContainer = document.getElementById("productContainer");
  if (productContainer) {
    const pathParts = window.location.pathname.split("/");
    const productId = pathParts[pathParts.length - 1];
    if (productId && productId !== "product.html" && productId !== "") {
      loadProductDetails(productId);
    }
  }
});