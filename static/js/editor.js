// VibeWrite Editor JavaScript

class VibeWriteEditor {
    constructor() {
        this.init();
    }

    init() {
        this.setupAutoResize();
        this.setupMarkdownHelpers();
        this.setupImageUpload();
        this.setupAutoSave();
    }

    setupAutoResize() {
        const textareas = document.querySelectorAll('textarea[data-auto-resize]');
        textareas.forEach(textarea => {
            textarea.addEventListener('input', this.autoResize);
            // Initial resize
            this.autoResize({ target: textarea });
        });
    }

    autoResize(event) {
        const textarea = event.target;
        textarea.style.height = 'auto';
        textarea.style.height = textarea.scrollHeight + 'px';
    }

    setupMarkdownHelpers() {
        // Add markdown formatting buttons if needed
        const markdownToolbar = document.getElementById('markdown-toolbar');
        if (markdownToolbar) {
            this.createMarkdownToolbar(markdownToolbar);
        }
    }

    createMarkdownToolbar(toolbar) {
        const buttons = [
            { icon: 'fas fa-heading', action: this.insertHeading, title: 'Heading' },
            { icon: 'fas fa-bold', action: this.insertBold, title: 'Bold' },
            { icon: 'fas fa-italic', action: this.insertItalic, title: 'Italic' },
            { icon: 'fas fa-link', action: this.insertLink, title: 'Link' },
            { icon: 'fas fa-image', action: this.insertImage, title: 'Image' },
            { icon: 'fas fa-list-ul', action: this.insertList, title: 'List' },
            { icon: 'fas fa-code', action: this.insertCode, title: 'Code' }
        ];

        buttons.forEach(btnConfig => {
            const button = document.createElement('button');
            button.type = 'button';
            button.className = 'btn btn-sm btn-outline-secondary me-1 mb-1';
            button.innerHTML = `<i class="${btnConfig.icon}"></i>`;
            button.title = btnConfig.title;
            button.addEventListener('click', btnConfig.action);
            toolbar.appendChild(button);
        });
    }

    insertHeading() {
        VibeWriteEditor.insertText('# Heading\n');
    }

    insertBold() {
        VibeWriteEditor.insertText('**bold text**');
    }

    insertItalic() {
        VibeWriteEditor.insertText('*italic text*');
    }

    insertLink() {
        VibeWriteEditor.insertText('[link text](https://)');
    }

    insertImage() {
        VibeWriteEditor.insertText('![alt text](https://)');
    }

    insertList() {
        VibeWriteEditor.insertText('- List item\n- Another item\n');
    }

    insertCode() {
        VibeWriteEditor.insertText('```\ncode here\n```');
    }

    static insertText(text) {
        const textarea = document.querySelector('textarea[data-auto-resize]');
        if (!textarea) return;

        const start = textarea.selectionStart;
        const end = textarea.selectionEnd;
        const selectedText = textarea.value.substring(start, end);
        
        let newText;
        if (selectedText) {
            newText = text.replace('text', selectedText);
        } else {
            newText = text;
        }

        textarea.value = textarea.value.substring(0, start) + newText + textarea.value.substring(end);
        textarea.focus();
        textarea.selectionStart = textarea.selectionEnd = start + newText.length;
        
        // Trigger auto-resize
        const event = new Event('input', { bubbles: true });
        textarea.dispatchEvent(event);
    }

    setupImageUpload() {
        const fileInputs = document.querySelectorAll('input[type="file"][data-preview]');
        fileInputs.forEach(input => {
            input.addEventListener('change', this.handleImagePreview);
        });
    }

    handleImagePreview(event) {
        const input = event.target;
        const previewId = input.dataset.preview;
        const preview = document.getElementById(previewId);
        const noImage = document.getElementById('no-image');

        if (input.files && input.files[0]) {
            const reader = new FileReader();
            reader.onload = function(e) {
                preview.src = e.target.result;
                preview.style.display = 'block';
                if (noImage) noImage.style.display = 'none';
            };
            reader.readAsDataURL(input.files[0]);
        }
    }

    setupAutoSave() {
        const textarea = document.querySelector('textarea[name="content"]');
        if (!textarea) return;

        let saveTimeout;
        textarea.addEventListener('input', () => {
            clearTimeout(saveTimeout);
            saveTimeout = setTimeout(() => {
                this.saveDraft();
            }, 2000);
        });
    }

    saveDraft() {
        const form = document.querySelector('form');
        if (!form) return;

        const formData = new FormData(form);
        
        // Show saving indicator
        this.showSavingIndicator();

        fetch('/api/save-draft', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                this.showSaveSuccess();
            }
        })
        .catch(error => {
            console.error('Auto-save failed:', error);
        });
    }

    showSavingIndicator() {
        // Implement saving indicator UI
        console.log('Saving...');
    }

    showSaveSuccess() {
        // Implement save success indicator
        console.log('Draft saved successfully');
    }
}

// Character counter for text areas
class CharacterCounter {
    constructor(textarea, counterElement, maxLength) {
        this.textarea = textarea;
        this.counter = counterElement;
        this.maxLength = maxLength;
        this.init();
    }

    init() {
        this.updateCounter();
        this.textarea.addEventListener('input', () => this.updateCounter());
    }

    updateCounter() {
        const length = this.textarea.value.length;
        this.counter.textContent = `${length}/${this.maxLength}`;
        
        if (length > this.maxLength * 0.9) {
            this.counter.classList.add('text-warning');
        } else {
            this.counter.classList.remove('text-warning');
        }
        
        if (length > this.maxLength) {
            this.counter.classList.add('text-danger');
        } else {
            this.counter.classList.remove('text-danger');
        }
    }
}

// Tag input functionality
class TagManager {
    constructor(input, container) {
        this.input = input;
        this.container = container;
        this.tags = [];
        this.init();
    }

    init() {
        this.input.addEventListener('keydown', (e) => this.handleKeydown(e));
        this.input.addEventListener('blur', () => this.addTag());
        
        // Load existing tags from input value
        if (this.input.value) {
            this.tags = this.input.value.split(',').map(tag => tag.trim()).filter(tag => tag);
            this.renderTags();
        }
    }

    handleKeydown(event) {
        if (event.key === 'Enter' || event.key === ',') {
            event.preventDefault();
            this.addTag();
        } else if (event.key === 'Backspace' && this.input.value === '' && this.tags.length > 0) {
            this.removeTag(this.tags.length - 1);
        }
    }

    addTag() {
        const tag = this.input.value.trim().replace(',', '');
        if (tag && !this.tags.includes(tag)) {
            this.tags.push(tag);
            this.renderTags();
        }
        this.input.value = '';
    }

    removeTag(index) {
        this.tags.splice(index, 1);
        this.renderTags();
    }

    renderTags() {
        this.container.innerHTML = '';
        this.tags.forEach((tag, index) => {
            const tagElement = document.createElement('span');
            tagElement.className = 'tag me-2 mb-2';
            tagElement.innerHTML = `
                ${tag}
                <button type="button" class="btn-close btn-close-white ms-1" 
                        onclick="tagManager.removeTag(${index})"></button>
            `;
            this.container.appendChild(tagElement);
        });
        
        // Update hidden input
        this.input.value = this.tags.join(', ');
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Initialize editor
    new VibeWriteEditor();

    // Initialize character counters
    const textareas = document.querySelectorAll('textarea[data-max-length]');
    textareas.forEach(textarea => {
        const counterId = textarea.dataset.counterId;
        const counter = document.getElementById(counterId);
        const maxLength = parseInt(textarea.dataset.maxLength);
        if (counter && maxLength) {
            new CharacterCounter(textarea, counter, maxLength);
        }
    });

    // Initialize tag manager
    const tagInput = document.querySelector('input[name="tags"]');
    const tagContainer = document.getElementById('tag-container');
    if (tagInput && tagContainer) {
        window.tagManager = new TagManager(tagInput, tagContainer);
    }

    // Markdown preview toggle
    const previewToggle = document.getElementById('markdown-toggle');
    if (previewToggle) {
        previewToggle.addEventListener('click', function() {
            const editor = document.getElementById('content');
            const preview = document.getElementById('markdown-preview');
            
            if (preview.style.display === 'none') {
                // Convert markdown to HTML
                preview.innerHTML = markdownToHtml(editor.value);
                preview.style.display = 'block';
                editor.style.display = 'none';
                this.innerHTML = '<i class="fas fa-edit me-2"></i>Edit';
            } else {
                preview.style.display = 'none';
                editor.style.display = 'block';
                this.innerHTML = '<i class="fas fa-eye me-2"></i>Preview';
            }
        });
    }
});

// Simple markdown to HTML converter
function markdownToHtml(text) {
    if (!text) return '';
    
    return text
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.*?)\*/g, '<em>$1</em>')
        .replace(/`(.*?)`/g, '<code>$1</code>')
        .replace(/\[(.*?)\]\((.*?)\)/g, '<a href="$2" target="_blank">$1</a>')
        .replace(/!\[(.*?)\]\((.*?)\)/g, '<img src="$2" alt="$1" class="img-fluid">')
        .replace(/^# (.*$)/gm, '<h1>$1</h1>')
        .replace(/^## (.*$)/gm, '<h2>$1</h2>')
        .replace(/^### (.*$)/gm, '<h3>$1</h3>')
        .replace(/^- (.*$)/gm, '<li>$1</li>')
        .replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>')
        .replace(/\n/g, '<br>');
}