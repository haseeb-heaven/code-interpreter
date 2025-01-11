document.addEventListener('DOMContentLoaded', function() {
    // Initialize CodeMirror for code input
    const codeEditor = CodeMirror.fromTextArea(document.getElementById('code'), {
        mode: 'python',
        theme: 'monokai',
        lineNumbers: true,
        indentUnit: 4,
        viewportMargin: Infinity,
        extraKeys: {
            'Tab': function(cm) {
                cm.replaceSelection('    ', 'end');
            }
        }
    });

    // Elements
    const themeSelect = document.getElementById('theme-select');
    const generateBtn = document.getElementById('generate-btn');
    const executeBtn = document.getElementById('execute-btn');
    const fixBtn = document.getElementById('fix-btn');
    const saveBtn = document.getElementById('save-btn');
    const editBtn = document.getElementById('edit-btn');
    const promptInput = document.getElementById('prompt');
    const modeSelect = document.getElementById('mode');
    const modelSelect = document.getElementById('model');
    const languageSelect = document.getElementById('language');
    const outputArea = document.getElementById('output');

    // Load theme preference
    const savedTheme = localStorage.getItem('theme') || 'light';
    themeSelect.value = savedTheme;
    document.body.classList.toggle('dark-theme', savedTheme === 'dark');

    // Theme toggle
    themeSelect.addEventListener('change', function() {
        const theme = this.value;
        document.body.classList.toggle('dark-theme', theme === 'dark');
        localStorage.setItem('theme', theme);
        showNotification('Theme updated successfully', 'success');
    });

    // Notification system
    function showNotification(message, type = 'info') {
        const notificationContainer = document.getElementById('notification-container');
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
    
    // Load models on page load
    loadModels();

    // Generate button
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
                    language: languageSelect.value
                })
            });

            if (!response.ok) throw new Error('Failed to generate code');
            const data = await response.json();
            if (data.error) throw new Error(data.error);

            codeEditor.setValue(data.response);
            showNotification('Code generated successfully', 'success');
        } catch (error) {
            showNotification(error.message, 'error');
        } finally {
            generateBtn.disabled = false;
        }
    });

    // Execute button
    executeBtn.addEventListener('click', async () => {
        const code = codeEditor.getValue().trim();
        if (!code) {
            showNotification('Please enter code to execute', 'error');
            return;
        }

        try {
            executeBtn.disabled = true;
            showNotification('Executing code...', 'info');

            const response = await fetch('/execute', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ code })
            });

            if (!response.ok) throw new Error('Failed to execute code');
            const data = await response.json();
            if (data.error) throw new Error(data.error);

            outputArea.value = data.result;
            showNotification('Code executed successfully', 'success');
        } catch (error) {
            showNotification(error.message, 'error');
            outputArea.value = error.message;
        } finally {
            executeBtn.disabled = false;
        }
    });

    // Fix button
    fixBtn.addEventListener('click', async () => {
        const code = codeEditor.getValue().trim();
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

            codeEditor.setValue(data.fixed_code);
            showNotification('Code fixed successfully', 'success');
        } catch (error) {
            showNotification(error.message, 'error');
        } finally {
            fixBtn.disabled = false;
        }
    });

    // Save button
    saveBtn.addEventListener('click', async () => {
        const code = codeEditor.getValue().trim();
        if (!code) {
            showNotification('Please enter code to save', 'error');
            return;
        }

        try {
            saveBtn.disabled = true;
            showNotification('Saving code...', 'info');

            const response = await fetch('/save_code', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ code })
            });

            if (!response.ok) throw new Error('Failed to save code');
            const data = await response.json();
            if (data.error) throw new Error(data.error);

            showNotification(data.result, 'success');
        } catch (error) {
            showNotification(error.message, 'error');
        } finally {
            saveBtn.disabled = false;
        }
    });

    // Edit button
    editBtn.addEventListener('click', () => {
        const isReadOnly = codeEditor.getOption('readOnly');
        codeEditor.setOption('readOnly', !isReadOnly);
        editBtn.textContent = isReadOnly ? 'Lock' : 'Edit';
        showNotification(`Code editor is now ${isReadOnly ? 'editable' : 'locked'}`, 'info');
    });

    // Language change
    languageSelect.addEventListener('change', function() {
        const mode = this.value;
        codeEditor.setOption('mode', mode);
        showNotification(`Language changed to ${mode}`, 'info');
    });

    // Mode change
    modeSelect.addEventListener('change', function() {
        const mode = this.value;
        promptInput.placeholder = `Enter ${mode} prompt here...`;
        showNotification(`Mode changed to ${mode}`, 'info');
    });
});
