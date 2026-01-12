/**
 * Cloud Manager Application
 * Handles Telegram WebApp integration, Authentication, and Form management
 */
class CloudManagerApp {
    constructor() {
        // Initialize Telegram WebApp or fallback
        this.tg = window.Telegram?.WebApp || this.createMockTelegram();

        // UI Elements
        this.mainSection = document.getElementById('mainSection');
        this.formSection = document.getElementById('formSection');

        // Initialize the application
        this.init();
    }

    /**
     * Create a mock Telegram WebApp object for testing outside Telegram
     */
    createMockTelegram() {
        return {
            expand: () => { },
            ready: () => { },
            showAlert: (msg) => alert(msg),
            sendData: (data) => console.log('Telegram sendData:', data),
            themeParams: {},
            openLink: (url) => window.open(url, '_blank')
        };
    }

    /**
     * Main initialization sequence
     */
    init() {
        this.setupTelegram();
        this.setupTheme();
        this.setupAuthButtons();
        this.setupNavigation();
        this.setupForm();
        this.setupInputAnimations();
    }

    /**
     * Configure Telegram WebApp environment
     */
    setupTelegram() {
        try {
            this.tg.expand();
            this.tg.ready();
        } catch (e) {
            console.log('Running outside Telegram environment');
        }
    }

    /**
     * Apply Telegram theme colors to CSS variables
     */
    setupTheme() {
        document.documentElement.style.setProperty(
            '--tg-theme-link-color',
            this.tg.themeParams?.link_color || '#4a6cf7'
        );
    }

    /**
     * Manage button loading state with spinner
     * @param {HTMLElement} btn - The button element
     * @param {boolean} isLoading - Whether to show loading state
     */
    setButtonLoading(btn, isLoading) {
        if (isLoading) {
            // Save original content if not already saved
            if (!btn.dataset.originalContent) {
                btn.dataset.originalContent = btn.innerHTML;
            }
            btn.disabled = true;
            // Add spinner and loading text
            btn.innerHTML = '<span class="spinner"></span> Загрузка...';
        } else {
            btn.disabled = false;
            // Restore original content
            if (btn.dataset.originalContent) {
                btn.innerHTML = btn.dataset.originalContent;
            }
        }
    }

    /**
     * Setup consolidated authentication button handlers
     * Uses data attributes to determine provider and endpoint
     */
    setupAuthButtons() {
        const authButtons = document.querySelectorAll('.js-auth-btn');

        authButtons.forEach(btn => {
            btn.addEventListener('click', async () => {
                const provider = btn.dataset.provider;
                const url = btn.dataset.url;

                console.log(`${provider} Auth button clicked`);
                this.setButtonLoading(btn, true);

                try {
                    const response = await fetch(url, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' }
                    });

                    const data = await response.json();
                    this.handleAuthResponse(data, btn, provider);

                } catch (error) {
                    console.error(`${provider} OAuth error:`, error);
                    this.setButtonLoading(btn, false);
                    this.tg.showAlert(`Ошибка подключения к ${provider}: ${error.message}`);
                }
            });
        });
    }

    /**
     * Handle the response from auth initialization endpoints
     */
    handleAuthResponse(data, btn, provider) {
        if (data.success) {
            // Check for redirect URL
            const redirectUrl = data.auth_url;

            if (redirectUrl) {
                console.log('Redirecting to:', redirectUrl);
                window.location.href = redirectUrl;
            } else {
                // Fallback or specific logical branches if needed
                this.setButtonLoading(btn, false);
                this.tg.showAlert('Успешная инициализация, но URL для перехода не получен');
            }
        } else {
            // Revert state and show error
            this.setButtonLoading(btn, false);
            const errorMsg = data.error || 'Ошибка инициализации';
            this.tg.showAlert(errorMsg);
        }
    }

    /**
     * Setup navigation between Main and Form sections
     */
    setupNavigation() {
        // Handle choice cards click (Pangolin/Corax)
        document.querySelectorAll('.choice-card').forEach(card => {
            card.addEventListener('click', () => {
                const choice = card.dataset.choice;
                const hiddenInput = document.querySelector('.choice-hidden');

                if (hiddenInput) {
                    hiddenInput.value = choice;
                }

                this.switchPage('form');
            });
        });

        // Handle Back button
        document.querySelector('.back-btn')?.addEventListener('click', () => {
            this.switchPage('main');
        });
    }

    /**
     * Switch visible page with transition effect
     */
    switchPage(targetPage) {
        if (!this.mainSection || !this.formSection) return;

        const current = targetPage === 'form' ? this.mainSection : this.formSection;
        const next = targetPage === 'form' ? this.formSection : this.mainSection;

        current.classList.remove('active');

        setTimeout(() => {
            current.classList.add('hidden');
            next.classList.remove('hidden');

            // Small delay to trigger transition
            setTimeout(() => {
                next.classList.add('active');
            }, 50);
        }, 300);
    }

    /**
     * Setup form submission
     */
    setupForm() {
        document.querySelector('.s-btn')?.addEventListener('click', () => {
            this.handleFormSubmit();
        });
    }

    /**
     * Validate and process form data
     */
    handleFormSubmit() {
        const titleInput = document.querySelector('.title-inp');
        const descInput = document.querySelector('.desc-inp');
        const subnetSelect = document.querySelector('.subnet-select');
        const flavorSelect = document.querySelector('.flavor-select');
        const choiceInput = document.querySelector('.choice-hidden');

        if (!titleInput || !subnetSelect || !flavorSelect) return;

        const title = titleInput.value.trim();
        const description = descInput ? descInput.value.trim() : '';
        const subnet = subnetSelect.value;
        const flavor = flavorSelect.value;
        const choice = choiceInput ? (choiceInput.value || "Не выбрано") : "Не выбрано";

        if (!subnet || !flavor) {
            this.tg.showAlert("Пожалуйста, выберите подсеть и конфигурацию");
            return;
        }

        if (!title) {
            this.tg.showAlert("Введите название виртуальной машины");
            return;
        }

        const data = { choice, title, desc: description, subnet, flavor };
        this.tg.sendData(JSON.stringify(data));

        // Show confirmation
        this.tg.showAlert(`Запрос на создание ВМ отправлен!\n\nСервис: ${choice}\nКонфигурация: ${flavor}\nПодсеть: ${subnet}`);
    }

    /**
     * Add focus effects to input fields
     */
    setupInputAnimations() {
        document.querySelectorAll('.input-field').forEach(input => {
            input.addEventListener('focus', () => {
                input.parentElement?.classList.add('focused');
            });
            input.addEventListener('blur', () => {
                if (!input.value) {
                    input.parentElement?.classList.remove('focused');
                }
            });
        });
    }
}

// Initialize on DOM Ready
document.addEventListener('DOMContentLoaded', () => {
    new CloudManagerApp();
});
