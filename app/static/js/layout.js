const header = document.querySelector('header');
const main = document.querySelector('main');
const searchInput = header.querySelector('input.search-bar');
const categoriesSection = main.querySelector('section.categories');
const productsSection = main.querySelector('section.products');


async function renderCategories() {
    const response = await fetch('ajax/render_categories');
    const html = await response.text();
    categoriesSection.innerHTML = html;
    // Bind click
    const catLi = categoriesSection.querySelectorAll('li');
    catLi.forEach(li => {
        li.addEventListener('click', () => {
            const currentActive = categoriesSection.querySelector('li.active');
            currentActive.classList.remove('active');
            li.classList.add('active');
            searchInput.value = '';
            renderProducts(li.dataset.id);
        })
    })
}

async function renderProducts(category="all", page=1) {
    const params = new URLSearchParams({
        category: category,
        query: searchInput.value,
        page: page
    });
    const response = await fetch(`ajax/render_products?${params}`);
    const html = await response.text();
    productsSection.innerHTML = html;
    // expose current product pagination page for trackers
    window.__currentProductPage = Number(page) || 1;
    // Bind click
    const products = productsSection.querySelectorAll('article');
    products.forEach(product => {
        product.addEventListener('click', () => {
            const currentActive = productsSection.querySelector('article.active');
            if (currentActive) {
                currentActive.classList.remove('active');
            }
            product.classList.add('active');
        })
    })
    // Bind pagination
    const paginationForm = main.querySelector('form.pagination');
    paginationForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const page = e.submitter.value;
        renderProducts(category, page);
    })
}



searchInput.addEventListener('change', () => {
    renderProducts();
})

renderCategories();
renderProducts();