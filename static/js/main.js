// Global variables
let currentPage = 1;
let currentFilters = {};

// Chat toggle function
function toggleChat() {
    const chatSidebar = document.getElementById('chatSidebar');
    if (chatSidebar) {
        chatSidebar.classList.toggle('open');
    }
}

// Product listing functions (for index.html)
if (typeof loadProducts !== 'undefined' || document.getElementById('productsGrid')) {
    // Load products on page load
    document.addEventListener('DOMContentLoaded', function() {
        if (typeof loadProducts === 'function') {
            loadProducts();
        }
        if (typeof loadCategories === 'function') {
            loadCategories();
        }
    });

    async function loadProducts(page = 1) {
        const loadingSpinner = document.getElementById('loadingSpinner');
        const productsGrid = document.getElementById('productsGrid');
        
        if (!productsGrid) return;
        
        if (loadingSpinner) loadingSpinner.classList.add('show');
        productsGrid.innerHTML = '';

        // Build query parameters
        const params = new URLSearchParams({
            page: page,
            page_size: 12,
            ...currentFilters
        });

        try {
            const response = await fetch(`/products?${params}`);
            const data = await response.json();

            // Update product count
            const productCount = document.getElementById('productCount');
            if (productCount) {
                productCount.textContent = `Showing ${data.products.length} of ${data.total} products`;
            }

            // Render products
            if (data.products.length === 0) {
                productsGrid.innerHTML = `
                    <div class="col-12">
                        <div class="alert alert-info text-center">
                            <i class="bi bi-inbox"></i> No products found. Try adjusting your filters.
                        </div>
                    </div>
                `;
            } else {
                data.products.forEach(product => {
                    const productCard = createProductCard(product);
                    productsGrid.appendChild(productCard);
                });
            }

            // Update pagination
            updatePagination(data.total, data.page, data.page_size);

        } catch (error) {
            console.error('Error loading products:', error);
            productsGrid.innerHTML = `
                <div class="col-12">
                    <div class="alert alert-danger">
                        <i class="bi bi-exclamation-triangle"></i> Error loading products. Please try again.
                    </div>
                </div>
            `;
        } finally {
            if (loadingSpinner) loadingSpinner.classList.remove('show');
        }
    }

    function createProductCard(product) {
        const col = document.createElement('div');
        col.className = 'col-md-4 col-sm-6 mb-4';

        const discountBadge = product.discount_percent 
            ? `<span class="discount-badge">${product.discount_percent}% OFF</span>` 
            : '';

        const stockBadgeClass = {
            'In Stock': 'bg-success',
            'Low Stock': 'bg-warning',
            'Out of Stock': 'bg-danger'
        }[product.stock_status] || 'bg-secondary';

        const stockBadge = product.stock_status 
            ? `<span class="badge ${stockBadgeClass} stock-badge">${product.stock_status}</span>` 
            : '';

        const mrpDisplay = product.mrp && product.mrp > product.price
            ? `<span class="mrp">₹${product.mrp.toLocaleString()}</span>`
            : '';

        col.innerHTML = `
            <div class="card product-card h-100">
                <img src="${product.primary_image || 'https://via.placeholder.com/400x400?text=No+Image'}" 
                     class="card-img-top product-image" 
                     alt="${product.title}"
                     onerror="this.src='https://via.placeholder.com/400x400?text=No+Image'">
                <div class="card-body d-flex flex-column">
                    <div class="mb-2">${stockBadge} ${discountBadge}</div>
                    <h6 class="card-title">${product.title}</h6>
                    <p class="text-muted small mb-2">
                        <i class="bi bi-tag"></i> ${product.brand || 'Unknown Brand'}
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
        const pagination = document.getElementById('pagination');
        if (!pagination) return;
        
        const totalPages = Math.ceil(total / pageSize);
        
        if (totalPages <= 1) {
            pagination.innerHTML = '';
            return;
        }

        let html = '';
        
        // Previous button
        html += `
            <li class="page-item ${page === 1 ? 'disabled' : ''}">
                <a class="page-link" href="#" onclick="loadProducts(${page - 1}); return false;">Previous</a>
            </li>
        `;

        // Page numbers
        for (let i = 1; i <= totalPages; i++) {
            if (i === 1 || i === totalPages || (i >= page - 2 && i <= page + 2)) {
                html += `
                    <li class="page-item ${i === page ? 'active' : ''}">
                        <a class="page-link" href="#" onclick="loadProducts(${i}); return false;">${i}</a>
                    </li>
                `;
            } else if (i === page - 3 || i === page + 3) {
                html += `<li class="page-item disabled"><span class="page-link">...</span></li>`;
            }
        }

        // Next button
        html += `
            <li class="page-item ${page === totalPages ? 'disabled' : ''}">
                <a class="page-link" href="#" onclick="loadProducts(${page + 1}); return false;">Next</a>
            </li>
        `;

        pagination.innerHTML = html;
    }

    function applyFilters() {
        currentFilters = {};
        
        const brand = document.getElementById('filterBrand');
        if (brand && brand.value.trim()) currentFilters.brand = brand.value.trim();

        const minPrice = document.getElementById('minPrice');
        if (minPrice && minPrice.value) currentFilters.min_price = parseFloat(minPrice.value);

        const maxPrice = document.getElementById('maxPrice');
        if (maxPrice && maxPrice.value) currentFilters.max_price = parseFloat(maxPrice.value);

        const stock = document.getElementById('filterStock');
        if (stock && stock.value) currentFilters.stock_status = stock.value;

        const category = document.getElementById('filterCategory');
        if (category && category.value) currentFilters.category_id = parseInt(category.value);

        const sortBy = document.getElementById('sortBy');
        if (sortBy) {
            if (sortBy.value === 'price_desc') {
                currentFilters.sort_by = 'price';
                currentFilters.sort_order = 'desc';
            } else if (sortBy.value === 'price') {
                currentFilters.sort_by = 'price';
                currentFilters.sort_order = 'asc';
            } else if (sortBy.value === 'title') {
                currentFilters.sort_by = 'title';
                currentFilters.sort_order = 'asc';
            }
        }

        currentPage = 1;
        loadProducts(1);
    }

    function clearFilters() {
        const filterBrand = document.getElementById('filterBrand');
        const minPrice = document.getElementById('minPrice');
        const maxPrice = document.getElementById('maxPrice');
        const filterStock = document.getElementById('filterStock');
        const filterCategory = document.getElementById('filterCategory');
        const sortBy = document.getElementById('sortBy');
        
        if (filterBrand) filterBrand.value = '';
        if (minPrice) minPrice.value = '';
        if (maxPrice) maxPrice.value = '';
        if (filterStock) filterStock.value = '';
        if (filterCategory) filterCategory.value = '';
        if (sortBy) sortBy.value = 'product_id';
        
        currentFilters = {};
        currentPage = 1;
        loadProducts(1);
    }

    async function loadCategories() {
        // This would typically come from a categories endpoint
        // For now, we'll use a placeholder
        const categorySelect = document.getElementById('filterCategory');
        // Categories will be loaded from the API when available
    }

    // Make functions globally available
    window.loadProducts = loadProducts;
    window.applyFilters = applyFilters;
    window.clearFilters = clearFilters;
    window.loadCategories = loadCategories;
}

// Product detail page functions
if (document.getElementById('productContainer')) {
    // Get product ID from URL
    const pathParts = window.location.pathname.split('/');
    const productId = pathParts[pathParts.length - 1];

    // Load product details
    document.addEventListener('DOMContentLoaded', function() {
        if (productId && productId !== 'product.html' && productId !== '') {
            loadProductDetails(productId);
        } else {
            showError('Invalid product ID');
        }
    });

    async function loadProductDetails(productId) {
        const loadingSpinner = document.getElementById('loadingSpinner');
        const productDetails = document.getElementById('productDetails');
        const errorMessage = document.getElementById('errorMessage');

        try {
            const response = await fetch(`/products/${productId}`);
            
            if (!response.ok) {
                throw new Error('Product not found');
            }

            const product = await response.json();

            // Populate product information
            const productTitle = document.getElementById('productTitle');
            const productBrand = document.getElementById('productBrand');
            const productType = document.getElementById('productType');
            
            if (productTitle) productTitle.textContent = product.title;
            if (productBrand) productBrand.textContent = product.brand || 'Unknown Brand';
            if (productType) productType.textContent = product.product_type || 'N/A';

            // Stock badge
            const stockBadge = document.getElementById('stockBadge');
            if (stockBadge) {
                const stockClass = {
                    'In Stock': 'bg-success',
                    'Low Stock': 'bg-warning',
                    'Out of Stock': 'bg-danger'
                }[product.stock_status] || 'bg-secondary';
                stockBadge.className = `badge ${stockClass}`;
                stockBadge.textContent = product.stock_status || 'Unknown';
            }

            // Price
            const priceDisplay = document.getElementById('priceDisplay');
            if (priceDisplay) priceDisplay.textContent = `₹${product.price.toLocaleString()}`;

            const mrpDisplay = document.getElementById('mrpDisplay');
            if (mrpDisplay) {
                if (product.mrp && product.mrp > product.price) {
                    mrpDisplay.textContent = `MRP: ₹${product.mrp.toLocaleString()}`;
                    mrpDisplay.style.display = 'block';
                } else {
                    mrpDisplay.style.display = 'none';
                }
            }

            const discountBadge = document.getElementById('discountBadge');
            if (discountBadge) {
                if (product.discount_percent) {
                    discountBadge.innerHTML = `<span class="badge bg-danger">${product.discount_percent}% OFF</span>`;
                } else {
                    discountBadge.innerHTML = '';
                }
            }

            // Images
            const mainImage = document.getElementById('mainImage');
            const thumbnailContainer = document.getElementById('thumbnailContainer');
            
            if (product.images && product.images.length > 0) {
                if (mainImage) {
                    mainImage.src = product.images[0].image_url;
                    mainImage.alt = product.title;
                }
                
                if (thumbnailContainer) {
                    product.images.forEach((image, index) => {
                        const thumbnail = document.createElement('img');
                        thumbnail.src = image.image_url;
                        thumbnail.className = 'product-thumbnail' + (index === 0 ? ' active' : '');
                        thumbnail.onclick = () => {
                            if (mainImage) mainImage.src = image.image_url;
                            document.querySelectorAll('.product-thumbnail').forEach(t => t.classList.remove('active'));
                            thumbnail.classList.add('active');
                        };
                        thumbnail.onerror = function() {
                            this.src = 'https://via.placeholder.com/100x100?text=Image';
                        };
                        thumbnailContainer.appendChild(thumbnail);
                    });
                }
            } else {
                if (mainImage) mainImage.src = 'https://via.placeholder.com/500x500?text=No+Image';
            }

            // Attributes
            const attributesTable = document.getElementById('attributesTable');
            if (attributesTable) {
                if (product.attributes && product.attributes.length > 0) {
                    product.attributes.forEach(attr => {
                        const row = document.createElement('tr');
                        row.innerHTML = `
                            <td><strong>${formatAttributeName(attr.attribute_name)}</strong></td>
                            <td>${attr.attribute_value || 'N/A'}</td>
                        `;
                        attributesTable.appendChild(row);
                    });
                } else {
                    attributesTable.innerHTML = '<tr><td colspan="2" class="text-muted">No attributes available</td></tr>';
                }
            }

            // Enable/disable add to cart
            const addToCartBtn = document.getElementById('addToCartBtn');
            if (addToCartBtn) {
                if (product.stock_status === 'Out of Stock') {
                    addToCartBtn.disabled = true;
                    addToCartBtn.textContent = 'Out of Stock';
                }
            }

            if (loadingSpinner) loadingSpinner.style.display = 'none';
            if (productDetails) productDetails.style.display = 'block';

        } catch (error) {
            console.error('Error loading product:', error);
            if (loadingSpinner) loadingSpinner.style.display = 'none';
            if (errorMessage) {
                errorMessage.style.display = 'block';
                const errorText = document.getElementById('errorText');
                if (errorText) errorText.textContent = error.message || 'Failed to load product details';
            }
        }
    }

    function formatAttributeName(name) {
        return name
            .split('_')
            .map(word => word.charAt(0).toUpperCase() + word.slice(1))
            .join(' ');
    }

    function showError(message) {
        const loadingSpinner = document.getElementById('loadingSpinner');
        const errorMessage = document.getElementById('errorMessage');
        const errorText = document.getElementById('errorText');
        
        if (loadingSpinner) loadingSpinner.style.display = 'none';
        if (errorMessage) errorMessage.style.display = 'block';
        if (errorText) errorText.textContent = message;
    }
}

