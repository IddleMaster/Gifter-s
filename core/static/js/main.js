/**
* Template Name: BizLand
* Template URL: https://bootstrapmade.com/bizland-bootstrap-business-template/
* Updated: Aug 07 2024 with Bootstrap v5.3.3
* Author: BootstrapMade.com
* License: https://bootstrapmade.com/license/
*/

(function () {
  "use strict";

  /**
   * Apply .scrolled class to the body as the page is scrolled down
   */

  /**
   * Mobile nav toggle
   */
  const mobileNavToggleBtn = document.querySelector('.mobile-nav-toggle');

  function mobileNavToogle() {
    document.querySelector('body').classList.toggle('mobile-nav-active');
    mobileNavToggleBtn.classList.toggle('bi-list');
    mobileNavToggleBtn.classList.toggle('bi-x');
  }
  mobileNavToggleBtn.addEventListener('click', mobileNavToogle);

  /**
   * Hide mobile nav on same-page/hash links
   */
  document.querySelectorAll('#navmenu a').forEach(navmenu => {
    navmenu.addEventListener('click', () => {
      if (document.querySelector('.mobile-nav-active')) {
        mobileNavToogle();
      }
    });

  });

  /**
   * Toggle mobile nav dropdowns
   */
  document.querySelectorAll('.navmenu .toggle-dropdown').forEach(navmenu => {
    navmenu.addEventListener('click', function (e) {
      e.preventDefault();
      this.parentNode.classList.toggle('active');
      this.parentNode.nextElementSibling.classList.toggle('dropdown-active');
      e.stopImmediatePropagation();
    });
  });

  /**
   * Preloader
   */
  const preloader = document.querySelector('#preloader');
  if (preloader) {
    window.addEventListener('load', () => {
      preloader.remove();
    });
  }

  /**
   * Scroll top button
   */
  let scrollTop = document.querySelector('.scroll-top');

  function toggleScrollTop() {
    if (scrollTop) {
      window.scrollY > 100 ? scrollTop.classList.add('active') : scrollTop.classList.remove('active');
    }
  }
  scrollTop.addEventListener('click', (e) => {
    e.preventDefault();
    window.scrollTo({
      top: 0,
      behavior: 'smooth'
    });
  });

  window.addEventListener('load', toggleScrollTop);
  document.addEventListener('scroll', toggleScrollTop);

  /**
   * Animation on scroll function and init
   */
  function aosInit() {
    AOS.init({
      duration: 600,
      easing: 'ease-in-out',
      once: true,
      mirror: false
    });
  }
  window.addEventListener('load', aosInit);

  /**
   * Initiate glightbox
   */
  const glightbox = GLightbox({
    selector: '.glightbox'
  });

  /**
   * Animate the skills items on reveal
   */
  let skillsAnimation = document.querySelectorAll('.skills-animation');
  skillsAnimation.forEach((item) => {
    new Waypoint({
      element: item,
      offset: '80%',
      handler: function (direction) {
        let progress = item.querySelectorAll('.progress .progress-bar');
        progress.forEach(el => {
          el.style.width = el.getAttribute('aria-valuenow') + '%';
        });
      }
    });
  });

  /**
   * Initiate Pure Counter
   */
  new PureCounter();

  /**
   * Init swiper sliders
   */
  function initSwiper() {
    document.querySelectorAll(".init-swiper").forEach(function (swiperElement) {
      let config = JSON.parse(
        swiperElement.querySelector(".swiper-config").innerHTML.trim()
      );

      if (swiperElement.classList.contains("swiper-tab")) {
        initSwiperWithCustomPagination(swiperElement, config);
      } else {
        new Swiper(swiperElement, config);
      }
    });
  }

  window.addEventListener("load", initSwiper);

  /**
   * Init isotope layout and filters
   */
  document.querySelectorAll('.isotope-layout').forEach(function (isotopeItem) {
    let layout = isotopeItem.getAttribute('data-layout') ?? 'masonry';
    let filter = isotopeItem.getAttribute('data-default-filter') ?? '*';
    let sort = isotopeItem.getAttribute('data-sort') ?? 'original-order';

    let initIsotope;
    imagesLoaded(isotopeItem.querySelector('.isotope-container'), function () {
      initIsotope = new Isotope(isotopeItem.querySelector('.isotope-container'), {
        itemSelector: '.isotope-item',
        layoutMode: layout,
        filter: filter,
        sortBy: sort
      });
    });

    isotopeItem.querySelectorAll('.isotope-filters li').forEach(function (filters) {
      filters.addEventListener('click', function () {
        isotopeItem.querySelector('.isotope-filters .filter-active').classList.remove('filter-active');
        this.classList.add('filter-active');
        initIsotope.arrange({
          filter: this.getAttribute('data-filter')
        });
        if (typeof aosInit === 'function') {
          aosInit();
        }
      }, false);
    });

  });

  /**
   * Frequently Asked Questions Toggle
   */
  document.querySelectorAll('.faq-item h3, .faq-item .faq-toggle').forEach((faqItem) => {
    faqItem.addEventListener('click', () => {
      faqItem.parentNode.classList.toggle('faq-active');
    });
  });

  /**
   * Correct scrolling position upon page load for URLs containing hash links.
   */
  window.addEventListener('load', function (e) {
    if (window.location.hash) {
      if (document.querySelector(window.location.hash)) {
        setTimeout(() => {
          let section = document.querySelector(window.location.hash);
          let scrollMarginTop = getComputedStyle(section).scrollMarginTop;
          window.scrollTo({
            top: section.offsetTop - parseInt(scrollMarginTop),
            behavior: 'smooth'
          });
        }, 100);
      }
    }
  });

  /**
   * Navmenu Scrollspy
   */
  let navmenulinks = document.querySelectorAll('.navmenu a');

  function navmenuScrollspy() {
    navmenulinks.forEach(navmenulink => {
      if (!navmenulink.hash) return;
      let section = document.querySelector(navmenulink.hash);
      if (!section) return;
      let position = window.scrollY + 200;
      if (position >= section.offsetTop && position <= (section.offsetTop + section.offsetHeight)) {
        document.querySelectorAll('.navmenu a.active').forEach(link => link.classList.remove('active'));
        navmenulink.classList.add('active');
      } else {
        navmenulink.classList.remove('active');
      }
    })
  }
  window.addEventListener('load', navmenuScrollspy);
  document.addEventListener('scroll', navmenuScrollspy);

})();


// ===== SISTEMA DE SUGERENCIAS DE BÚSQUEDA =====

function inicializarSugerenciasBusqueda() {
  console.log('🔍 Inicializando sistema de sugerencias...');

  const searchConfigs = [
    { input: 'searchInputDesktop', container: 'sugerenciasDesktop' },
    { input: 'searchInputMobile', container: 'sugerenciasMobile' }
  ];

  let timeoutId;
  const DEBOUNCE_DELAY = 300;

  searchConfigs.forEach(config => {
    const searchInput = document.getElementById(config.input);
    const sugerenciasContainer = document.getElementById(config.container);

    console.log(`Buscando elementos: ${config.input} y ${config.container}`);
    console.log('Input encontrado:', searchInput);
    console.log('Container encontrado:', sugerenciasContainer);

    if (!searchInput || !sugerenciasContainer) {
      console.error(`❌ No se encontraron los elementos: ${config.input} o ${config.container}`);
      return;
    }

    // Añadir estilos de debug temporalmente
    sugerenciasContainer.style.border = '2px solid red';
    sugerenciasContainer.style.background = '#fff0f0';

    // Evento de input con debounce
    searchInput.addEventListener('input', function (e) {
      const query = e.target.value.trim();
      console.log(`📝 Input cambiado: "${query}"`);

      clearTimeout(timeoutId);

      if (query.length < 2) {
        console.log('❌ Query muy corta, ocultando sugerencias');
        sugerenciasContainer.style.display = 'none';
        return;
      }

      timeoutId = setTimeout(() => {
        console.log(`🔍 Buscando sugerencias para: "${query}"`);
        buscarSugerencias(query, sugerenciasContainer);
      }, DEBOUNCE_DELAY);
    });

    // Ocultar sugerencias al hacer clic fuera
    document.addEventListener('click', function (e) {
      if (!searchInput.contains(e.target) && !sugerenciasContainer.contains(e.target)) {
        sugerenciasContainer.style.display = 'none';
      }
    });

    // Navegación con teclado
    searchInput.addEventListener('keydown', function (e) {
      const items = sugerenciasContainer.querySelectorAll('.sugerencia-item');

      if (e.key === 'ArrowDown' && items.length > 0) {
        e.preventDefault();
        items[0].focus();
      } else if (e.key === 'Escape') {
        sugerenciasContainer.style.display = 'none';
        searchInput.focus();
      }
    });

    // Cerrar sugerencias al enviar el formulario
    const form = searchInput.closest('form');
    if (form) {
      form.addEventListener('submit', function () {
        sugerenciasContainer.style.display = 'none';
      });
    }
  });

  function buscarSugerencias(query, container) {
    const url = `/buscar-sugerencias/?q=${encodeURIComponent(query)}`;
    console.log(`🌐 Haciendo petición a: ${url}`);

    fetch(url)
      .then(response => {
        console.log('📨 Respuesta recibida:', response.status);
        if (!response.ok) throw new Error('Error en la respuesta');
        return response.json();
      })
      .then(data => {
        console.log('✅ Datos recibidos:', data);
        mostrarSugerencias(data.sugerencias, container);
      })
      .catch(error => {
        console.error('❌ Error fetching suggestions:', error);
        container.style.display = 'none';
      });
  }

  function mostrarSugerencias(sugerencias, container) {
    console.log(`🎯 Mostrando ${sugerencias.length} sugerencias`);

    if (sugerencias.length === 0) {
      console.log('📭 No hay sugerencias, ocultando container');
      container.style.display = 'none';
      return;
    }

    container.innerHTML = '';

    // Añadir un título de debug temporal
    const debugHeader = document.createElement('div');
    debugHeader.style.padding = '0.5rem 1rem';
    debugHeader.style.background = '#ffeb3b';
    debugHeader.style.fontSize = '0.8rem';
    debugHeader.style.borderBottom = '1px solid #ccc';
    debugHeader.textContent = `🔍 ${sugerencias.length} sugerencias encontradas`;
    container.appendChild(debugHeader);

    sugerencias.forEach((sugerencia, index) => {
      console.log(`📦 Sugerencia ${index + 1}:`, sugerencia);

      const item = document.createElement('a');
      item.href = sugerencia.url;
      item.className = 'sugerencia-item';
      item.tabIndex = 0;
      item.style.border = '1px solid blue'; // Debug visual

      // Construir contenido según el tipo
      let metaHTML = '';
      let descripcionHTML = '';

      if (sugerencia.tipo === 'producto') {
        if (sugerencia.marca || sugerencia.categoria) {
          metaHTML = `<div class="sugerencia-meta">`;
          if (sugerencia.marca) {
            metaHTML += `<span class="marca">${sugerencia.marca}</span>`;
          }
          if (sugerencia.marca && sugerencia.categoria) {
            metaHTML += ` • `;
          }
          if (sugerencia.categoria) {
            metaHTML += `<span class="categoria">${sugerencia.categoria}</span>`;
          }
          metaHTML += `</div>`;
        }
      } else if (sugerencia.tipo === 'categoría' && sugerencia.descripcion) {
        descripcionHTML = `<div class="sugerencia-descripcion">${sugerencia.descripcion}</div>`;
      }

      item.innerHTML = `
                <div class="sugerencia-header">
                    <span class="sugerencia-tipo ${sugerencia.tipo}">${sugerencia.tipo}</span>
                    <span class="sugerencia-texto">${sugerencia.texto}</span>
                </div>
                ${metaHTML}
                ${descripcionHTML}
            `;

      // Al hacer clic, redirigir
      item.addEventListener('click', function (e) {
        e.preventDefault();
        console.log(`🖱️ Clic en sugerencia: ${sugerencia.url}`);
        window.location.href = this.href;
      });

      container.appendChild(item);
    });

    console.log('👁️ Mostrando container de sugerencias');
    container.style.display = 'block';

    // Debug: mostrar posición y tamaño
    console.log('📍 Posición del container:', container.getBoundingClientRect());
  }
}

// Inicializar cuando el DOM esté listo
document.addEventListener('DOMContentLoaded', function () {
  console.log('🚀 DOM cargado, inicializando sugerencias...');
  inicializarSugerenciasBusqueda();
});


//feed
document.addEventListener('DOMContentLoaded', function () {
  // --- LÍNEA DE PRUEBA 1 ---
  console.log("El script del feed se está ejecutando.");

  const likeButtons = document.querySelectorAll('.like-btn');

  // --- LÍNEA DE PRUEBA 2 ---
  console.log("Botones de 'like' encontrados:", likeButtons);

  likeButtons.forEach(button => {
    button.addEventListener('click', function (event) {
      event.preventDefault();

      const postId = this.dataset.postId;
      const url = `/post/${postId}/like/`;
      const csrfToken = document.querySelector('form [name=csrfmiddlewaretoken]').value;

      fetch(url, {
        method: 'POST',
        headers: {
          'X-CSRFToken': csrfToken,
          'Content-Type': 'application/json'
        },
      })
        .then(response => response.json())
        .then(data => {
          if (data.error) {
            console.error("Error desde el servidor:", data.error);
            return;
          }
          const likeCountSpan = this.querySelector('.like-count');
          likeCountSpan.textContent = data.total_likes;
          this.classList.toggle('liked', data.liked);
        })
        .catch(error => console.error('Error en fetch:', error));
    });
  });
});


