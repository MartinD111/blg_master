function initApp() {
    initTheme();
    initLanguage();
    initActiveNav();
}

document.addEventListener('DOMContentLoaded', initApp);
document.addEventListener('htmx:afterSwap', initApp);

// --- Active Nav Logic ---
function initActiveNav() {
    // Disabled per user request
    /*
    const path = window.location.pathname;
    const links = document.querySelectorAll('.nav-link, .dropdown-link');

    links.forEach(link => {
        const href = link.getAttribute('href');
        if (href && href !== '#' && path.includes(href.replace('{{ url_for(', '').replace(') }}', ''))) {
            link.classList.add('text-primary', 'dark:text-primary-dark', 'font-bold');

            // If it's in a dropdown/flyout, we might want to highlight the parent too
            let parent = link.closest('.nav-item');
            if (parent) {
                const parentLink = parent.querySelector('.nav-link');
                if (parentLink) parentLink.classList.add('text-primary', 'dark:text-primary-dark');
            }
        }
    });
    */
}


// --- Theme Logic ---
function initTheme() {
    // Check localStorage or System Preference
    if (localStorage.theme === 'dark' || (!('theme' in localStorage) && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
        document.documentElement.classList.add('dark');
    } else {
        document.documentElement.classList.remove('dark');
    }
}

function toggleTheme() {
    const html = document.documentElement;
    if (html.classList.contains('dark')) {
        html.classList.remove('dark');
        localStorage.theme = 'light';
    } else {
        html.classList.add('dark');
        localStorage.theme = 'dark';
    }
}

// --- Language Logic ---
const TEXTS = {
    en: {
        productivity: "Productivity",
        workload: "Daily Work Load",
        project: "Top Project",
        settings: "Settings",
        theme: "Theme",
        language: "Language",
        avatar: "Choose Avatar",
        role: "Role: Administrator"
    },
    sl: {
        productivity: "Produktivnost",
        workload: "Dnevna Obremenitev",
        project: "Top Projekt",
        settings: "Nastavitve",
        theme: "Tema",
        language: "Jezik",
        avatar: "Izberi Avatar",
        role: "Vloga: Administrator"
    }
};

function initLanguage() {
    const lang = localStorage.getItem('language') || 'en';
    applyLanguage(lang);
}

function toggleLanguage() {
    const current = localStorage.getItem('language') || 'en';
    const next = current === 'en' ? 'sl' : 'en';
    localStorage.setItem('language', next);
    applyLanguage(next);
}

function applyLanguage(lang) {
    document.documentElement.lang = lang;
    const texts = TEXTS[lang];
    if (!texts) return;

    // Example simple text replacement for Profile Page elements if they exist
    // In a real app, use a proper i18n library. here we target data-i18n attributes.
    document.querySelectorAll('[data-i18n]').forEach(el => {
        const key = el.getAttribute('data-i18n');
        if (texts[key]) el.textContent = texts[key];
    });

    // Update button text if specific IDs exist
    const langLabel = document.getElementById('lang-label');
    if (langLabel) langLabel.textContent = lang === 'en' ? 'English' : 'Slovenian';
}
