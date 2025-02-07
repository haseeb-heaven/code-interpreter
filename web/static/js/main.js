document.addEventListener('DOMContentLoaded', function() {
    // Get DOM elements
    const promptInput = document.getElementById('prompt');
    const codeEditor = document.getElementById('code');
    const outputArea = document.getElementById('output');
    const generateBtn = document.getElementById('generate-btn');
    const executeBtn = document.getElementById('execute-btn');
    const fixBtn = document.getElementById('fix-btn');
    const editBtn = document.getElementById('edit-btn');
    const clearBtn = document.getElementById('clear-btn');
    const copyBtn = document.getElementById('copy-btn');
    const modelSelect = document.getElementById('model');
    const modeSelect = document.getElementById('mode');
    const languageSelect = document.getElementById('language');
    const displayCodeCheckbox = document.getElementById('display-code');
    const executeCodeCheckbox = document.getElementById('execute-code');
    const codeBlock = document.getElementById('code-block');
    const filesInput = document.getElementById('files');
    const folderInput = document.getElementById('folder');
    const selectFilesBtn = document.getElementById('select-files');
    const selectFolderBtn = document.getElementById('select-folder');
    const themeSelect = document.getElementById('theme-select');
    const notificationContainer = document.getElementById('notification-container');
    const installBtn = document.getElementById('install-btn');
    const packageNameInput = document.getElementById('package-name');
    
    // Load theme preference
    const savedTheme = localStorage.getItem('theme') || 'light';
    themeSelect.value = savedTheme;
    document.body.classList.toggle('dark-theme', savedTheme === 'dark');

    // Theme toggle handler
    themeSelect.addEventListener('change', function() {
        const theme = this.value;
        document.body.classList.toggle('dark-theme', theme === 'dark');
        localStorage.setItem('theme', theme);
        showNotification('Theme updated', 'success');
    });

    // Function to show notifications
    function showNotification(message, type = 'info') {
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        
        const messageText = document.createElement('span');
        messageText.textContent = message;
        
        const closeBtn = document.createElement('button');
        closeBtn.textContent = '×';
        closeBtn.className = 'close-btn';
        closeBtn.onclick = () => notification.remove();
        
        notification.appendChild(messageText);
        notification.appendChild(closeBtn);
        notificationContainer.appendChild(notification);
        
        setTimeout(() => {
            notification.style.animation = 'fadeOut 0.5s ease-out';
            setTimeout(() => notification.remove(), 500);
        }, 5000);
    }

    // Display Code checkbox handler
    displayCodeCheckbox.addEventListener('change', function() {
        codeBlock.style.display = this.checked ? 'block' : 'none';
        console.log('Display code toggled:', this.checked);
    });

    // File selection handlers
    selectFilesBtn.addEventListener('click', () => {
        console.log('Select files button clicked');
        filesInput.click();
    });

    selectFolderBtn.addEventListener('click', () => {
        console.log('Select folder button clicked');
        folderInput.click();
    });

    // Function to format code based on language
    function formatCode(code, language) {
        const codeArea = document.getElementById('code');
        codeArea.className = `${language}-code`;
        
        // Basic syntax highlighting
        if (language === 'python') {
            code = code.replace(/(def|class|if|else|for|while|import|from|return|True|False|None)\b/g, '<span class="keyword">$1</span>')
                      .replace(/(["'])(.*?)\1/g, '<span class="string">$1$2$1</span>')
                      .replace(/\b(\d+)\b/g, '<span class="number">$1</span>')
                      .replace(/\b([a-zA-Z_]\w*)\(/g, '<span class="function">$1</span>(')
                      .replace(/#.*/g, '<span class="comment">$&</span>');
        } else if (language === 'javascript') {
            code = code.replace(/(function|const|let|var|if|else|for|while|return|true|false|null)\b/g, '<span class="keyword">$1</span>')
                      .replace(/(["'])(.*?)\1/g, '<span class="string">$1$2$1</span>')
                      .replace(/\b(\d+)\b/g, '<span class="number">$1</span>')
                      .replace(/\b([a-zA-Z_]\w*)\(/g, '<span class="function">$1</span>(')
                      .replace(/\/\/.*/g, '<span class="comment">$&</span>')
                      .replace(/\/\*[\s\S]*?\*\//g, '<span class="comment">$&</span>');
        }
        
        return code;
    }

    // Function to get absolute file path
    function getAbsolutePath(file) {
        if (file.path) {
            return file.path;
        }
        
        const fullPath = new URL(file.webkitRelativePath || file.name, window.location.href).pathname;
        return fullPath.startsWith('/') ? fullPath : '/' + fullPath;
    }

    // Install package handler
    installBtn.addEventListener('click', async () => {
        const packageName = packageNameInput.value.trim();
        if (!packageName) {
            showNotification('Please enter a package name', 'error');
            return;
        }

        try {
            installBtn.disabled = true;
            showNotification(`Installing package: ${packageName}...`, 'info');

            const response = await fetch('/install', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    package: packageName,
                    mode: modeSelect.value,
                    model: modelSelect.value,
                    language: languageSelect.value
                })
            });

            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.error || `Failed to install package: ${packageName}`);
            }
            if (data.error) {
                throw new Error(data.error);
            }

            showNotification(data.result || `Package ${packageName} installed successfully`, 'success');
            packageNameInput.value = '';
        } catch (error) {
            console.error('Install error:', error);
            showNotification(error.message, 'error');
        } finally {
            installBtn.disabled = false;
        }
    });

    // Modified file selection handler
    filesInput.addEventListener('change', (event) => {
        const files = Array.from(event.target.files);
        if (files.length > 0) {
            console.log('Selected files:', files);
            const paths = files.map(file => {
                const absolutePath = getAbsolutePath(file);
                console.log('Absolute file path:', absolutePath);
                return absolutePath;
            });
            
            const fileList = paths.join('\n');
            console.log('File list to append:', fileList);
            
            promptInput.value += (promptInput.value ? '\n\n' : '') + `Selected Files:\n${fileList}`;
            showNotification(`Added ${files.length} file(s)`, 'success');
        }
    });

    // Modified folder selection handler
    folderInput.addEventListener('change', (event) => {
        const files = Array.from(event.target.files);
        if (files.length > 0) {
            const folderPath = getAbsolutePath(files[0]).split('/').slice(0, -1).join('/');
            console.log('Selected folder path:', folderPath);
            
            promptInput.value += (promptInput.value ? '\n\n' : '') + `Selected Folder:\n${folderPath}`;
            showNotification('Added folder path', 'success');
        }
    });

    // Language change handler for code formatting
    languageSelect.addEventListener('change', function() {
        const code = codeEditor.value;
        if (code) {
            codeEditor.innerHTML = formatCode(code, this.value);
        }
    });

    // Function to get full file path
    function getFullPath(file) {
        if (file.path) {
            return file.path;
        }
        // For web API File objects, construct path from webkitRelativePath
        if (file.webkitRelativePath) {
            return '/' + file.webkitRelativePath;
        }
        // Fallback to filename
        return file.name;
    }

    // Fix button handler
    fixBtn.addEventListener('click', async () => {
        const code = codeEditor.value.trim();
        if (!code) {
            showNotification('Please enter code to fix', 'error');
            return;
        }

        try {
            fixBtn.disabled = true;
            showNotification('Fixing code...', 'info');

            const response = await fetch('/fix', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ code })
            });

            if (!response.ok) throw new Error('Failed to fix code');
            const data = await response.json();
            if (data.error) throw new Error(data.error);

            codeEditor.value = data.fixed_code;
            showNotification('Code fixed successfully', 'success');
        } catch (error) {
            showNotification(error.message, 'error');
        } finally {
            fixBtn.disabled = false;
        }
    });

    // Edit button handler
    editBtn.addEventListener('click', () => {
        const codeArea = document.getElementById('code');
        const isReadOnly = codeArea.readOnly;
        codeArea.readOnly = !isReadOnly;
        editBtn.textContent = isReadOnly ? 'Lock' : 'Edit';
        showNotification(`Code editor is now ${isReadOnly ? 'editable' : 'locked'}`, 'info');
    });

    // Generate button handler
    generateBtn.addEventListener('click', async () => {
        if (!promptInput.value.trim()) {
            showNotification('Please enter a prompt', 'error');
            return;
        }

        try {
            generateBtn.disabled = true;
            showNotification('Generating code...', 'info');

            const response = await fetch('/generate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    prompt: promptInput.value,
                    mode: modeSelect.value,
                    model: modelSelect.value,
                    language: languageSelect.value,
                    execute: executeCodeCheckbox.checked
                })
            });

            if (!response.ok) throw new Error('Failed to generate code');
            const data = await response.json();
            if (data.error) throw new Error(data.error);

            codeEditor.value = data.response;
            showNotification('Code generated successfully', 'success');

            if (executeCodeCheckbox.checked) {
                executeBtn.click();
            }
        } catch (error) {
            showNotification(error.message, 'error');
        } finally {
            generateBtn.disabled = false;
        }
    });

    // Execute button handler
    executeBtn.addEventListener('click', async () => {
        const code = codeEditor.value.trim();
        if (!code) {
            showNotification('No code to execute', 'error');
            return;
        }

        try {
            executeBtn.disabled = true;
            showNotification('Executing code...', 'info');

            const response = await fetch('/execute', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    code,
                    mode: modeSelect.value,
                    model: modelSelect.value,
                    language: languageSelect.value
                })
            });

            if (!response.ok) throw new Error('Failed to execute code');
            const data = await response.json();
            if (data.error) throw new Error(data.error);

            outputArea.value = data.result;
            
            // Handle special outputs if present
            if (data.special_outputs && data.special_outputs.length > 0) {
                displaySpecialOutput(data.special_outputs);
            }
            
            showNotification('Code executed successfully', 'success');
        } catch (error) {
            showNotification(error.message, 'error');
        } finally {
            executeBtn.disabled = false;
        }
    });

    // Clear button handler
    clearBtn.addEventListener('click', () => {
        promptInput.value = '';
        codeEditor.value = '';
        outputArea.value = '';
        showNotification('All fields cleared', 'info');
    });

    // Copy button handler
    copyBtn.addEventListener('click', () => {
        const code = codeEditor.value;
        if (code) {
            navigator.clipboard.writeText(code)
                .then(() => showNotification('Code copied to clipboard', 'success'))
                .catch(() => showNotification('Failed to copy code', 'error'));
        } else {
            showNotification('No code to copy', 'error');
        }
    });

    // Load models
    async function loadModels() {
        try {
            const response = await fetch('/get_models');
            if (!response.ok) throw new Error('Failed to fetch models');
            
            const data = await response.json();
            if (data.error) throw new Error(data.error);
            
            modelSelect.innerHTML = '';
            data.models.forEach(model => {
                const option = document.createElement('option');
                option.value = model;
                option.textContent = model;
                modelSelect.appendChild(option);
            });
            
            showNotification('Models loaded successfully', 'success');
        } catch (error) {
            showNotification(error.message, 'error');
        }
    }

    // Add this function after other function declarations
    function displaySpecialOutput(output) {
        const outputDiv = document.getElementById('special-output');
        
        if (!outputDiv) {
            const div = document.createElement('div');
            div.id = 'special-output';
            div.className = 'special-output';
            document.getElementById('output-container').appendChild(div);
        }
        
        outputDiv.innerHTML = ''; // Clear previous outputs
        
        output.forEach(item => {
            const container = document.createElement('div');
            container.className = 'special-output-item';
            
            const title = document.createElement('h4');
            title.textContent = item.title;
            container.appendChild(title);
            
            if (item.type === 'image') {
                const img = document.createElement('img');
                img.src = item.url;
                img.className = 'output-image';
                container.appendChild(img);
            } else if (item.type === 'html') {
                const div = document.createElement('div');
                div.innerHTML = item.content;
                div.className = 'output-table';
                container.appendChild(div);
            }
            
            outputDiv.appendChild(container);
        });
    }

    // Initialize display state
    codeBlock.style.display = displayCodeCheckbox.checked ? 'block' : 'none';
    document.getElementById('code').readOnly = true;
    
    // Load models on page load
    loadModels();
});
