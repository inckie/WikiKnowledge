/**
 * WikiKnowledge — Chip Input Component
 * Reusable tag/category chip input with autocomplete.
 */

class ChipInput {
    /**
     * @param {HTMLElement} container - The container element
     * @param {Object} options
     * @param {string} options.type - 'tag' or 'category' (affects styling)
     * @param {string} options.placeholder - Input placeholder text
     * @param {Function} options.fetchSuggestions - Async function returning suggestions
     * @param {Function} options.onChange - Callback when chips change
     */
    constructor(container, options = {}) {
        this.container = container;
        this.type = options.type || 'tag';
        this.placeholder = options.placeholder || 'Add...';
        this.fetchSuggestions = options.fetchSuggestions || (() => []);
        this.onChange = options.onChange || (() => {});
        this.chips = [];

        this._render();
        this._bindEvents();
    }

    _render() {
        this.container.innerHTML = '';
        this.container.className = 'chip-input-container';

        this.input = document.createElement('input');
        this.input.type = 'text';
        this.input.placeholder = this.placeholder;
        this.container.appendChild(this.input);
    }

    _bindEvents() {
        this.input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && this.input.value.trim()) {
                e.preventDefault();
                this.addChip(this.input.value.trim());
                this.input.value = '';
                this._hideAutocomplete();
            } else if (e.key === 'Backspace' && !this.input.value && this.chips.length) {
                this.removeChip(this.chips[this.chips.length - 1]);
            } else if (e.key === 'Escape') {
                this._hideAutocomplete();
            }
        });

        this.input.addEventListener('input', Utils.debounce(async () => {
            const val = this.input.value.trim();
            if (val.length < 1) {
                this._hideAutocomplete();
                return;
            }
            const suggestions = await this.fetchSuggestions(val);
            const filtered = suggestions.filter(s => !this.chips.includes(s));
            this._showAutocomplete(filtered);
        }, 200));

        this.input.addEventListener('focus', async () => {
            const val = this.input.value.trim();
            if (val.length >= 1) {
                const suggestions = await this.fetchSuggestions(val);
                const filtered = suggestions.filter(s => !this.chips.includes(s));
                this._showAutocomplete(filtered);
            }
        });

        this.container.addEventListener('click', () => this.input.focus());
    }

    addChip(value) {
        if (this.chips.includes(value)) return;
        this.chips.push(value);
        this._renderChips();
        this.onChange(this.chips);
    }

    removeChip(value) {
        this.chips = this.chips.filter(c => c !== value);
        this._renderChips();
        this.onChange(this.chips);
    }

    setChips(values) {
        this.chips = [...values];
        this._renderChips();
    }

    getChips() {
        return [...this.chips];
    }

    _renderChips() {
        // Remove existing chip elements
        this.container.querySelectorAll('.chip').forEach(el => el.remove());

        // Insert chips before the input
        this.chips.forEach(value => {
            const chip = document.createElement('span');
            chip.className = `chip chip-${this.type}`;
            chip.innerHTML = `${Utils.escapeHtml(value)}<span class="chip-remove">×</span>`;
            chip.querySelector('.chip-remove').addEventListener('click', (e) => {
                e.stopPropagation();
                this.removeChip(value);
            });
            this.container.insertBefore(chip, this.input);
        });
    }

    _showAutocomplete(items) {
        const dropdown = document.getElementById('autocomplete-dropdown');
        if (!items.length) {
            this._hideAutocomplete();
            return;
        }

        dropdown.innerHTML = items
            .slice(0, 10)
            .map(item => `<div class="autocomplete-item" data-value="${Utils.escapeHtml(item)}">${Utils.escapeHtml(item)}</div>`)
            .join('');

        // Position dropdown below the input container
        const rect = this.container.getBoundingClientRect();
        dropdown.style.top = `${rect.bottom + 4}px`;
        dropdown.style.left = `${rect.left}px`;
        dropdown.style.width = `${rect.width}px`;
        dropdown.classList.remove('hidden');

        // Click handlers
        dropdown.querySelectorAll('.autocomplete-item').forEach(el => {
            el.addEventListener('click', () => {
                this.addChip(el.dataset.value);
                this.input.value = '';
                this._hideAutocomplete();
            });
        });
    }

    _hideAutocomplete() {
        const dropdown = document.getElementById('autocomplete-dropdown');
        dropdown.classList.add('hidden');
    }
}

// Hide autocomplete when clicking elsewhere
document.addEventListener('click', (e) => {
    if (!e.target.closest('.chip-input-container') && !e.target.closest('.autocomplete-dropdown')) {
        document.getElementById('autocomplete-dropdown')?.classList.add('hidden');
    }
});
