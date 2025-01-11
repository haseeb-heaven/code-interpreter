document.addEventListener('DOMContentLoaded', function() {
    // Initialize CodeMirror
    const codeOutput = CodeMirror(document.getElementById('codeOutput'), {
        mode: 'python',
        theme: 'monokai',
        lineNumbers: true,
        readOnly: true,
        viewportMargin: Infinity
    });

    // Theme handling
    const themeSelect = document.getElementById('themeSelect');
    themeSelect.addEventListener('change', function() {
        document.body.setAttribute('data-theme', this.value);
    });

    // File upload handling
    const fileUploadArea = document.getElementById('fileUploadArea');
    const fileInput = document.getElementById('fileInput');
    const fileInfo = document.getElementById('fileInfo');
    let uploadedFiles = [];

    fileUploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        fileUploadArea.classList.add('dragover');
    });

    fileUploadArea.addEventListener('dragleave', () => {
        fileUploadArea.classList.remove('dragover');
    });

    fileUploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        fileUploadArea.classList.remove('dragover');
        const files = e.dataTransfer.files;
        handleFiles(files);
    });

    fileInput.addEventListener('change', (e) => {
        handleFiles(e.target.files);
    });

    function handleFiles(files) {
        uploadedFiles = Array.from(files);
        updateFileInfo();
    }

    function updateFileInfo() {
        if (uploadedFiles.length > 0) {
            const fileNames = uploadedFiles.map(file => `${file.name} (${formatFileSize(file.size)})`).join(', ');
            fileInfo.innerHTML = `
                <p>Files selected: ${uploadedFiles.length}</p>
                <p>${fileNames}</p>
            `;
        } else {
            fileInfo.innerHTML = '<p>Drop files here or click to upload</p>';
        }
    }

    function formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    // Mode handling
    const modeSelect = document.getElementById('modeSelect');
    const fileUploadSection = document.querySelector('.file-upload');

    modeSelect.addEventListener('change', function() {
        if (this.value === 'vision') {
            fileUploadSection.style.display = 'block';
            fileInput.accept = 'image/*';
        } else {
            fileUploadSection.style.display = 'none';
            fileInput.accept = '';
        }
    });

    // Language handling
    const languageSelect = document.getElementById('languageSelect');
    languageSelect.addEventListener('change', function() {
        codeOutput.setOption('mode', this.value);
    });

    // Generate button
    document.getElementById('generateBtn').addEventListener('click', async () => {
        const prompt = document.getElementById('promptInput').value;
        const mode = modeSelect.value;
        const model = document.getElementById('modelSelect').value;
        const language = languageSelect.value;

        try {
            const response = await fetch('/generate', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ prompt, mode, model, language })
            });
            const data = await response.json();
            codeOutput.setValue(data.response);
        } catch (error) {
            console.error('Error:', error);
        }
    });

    // Execute button
    document.getElementById('executeBtn').addEventListener('click', async () => {
        const code = codeOutput.getValue();
        try {
            const response = await fetch('/execute', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ code })
            });
            const data = await response.json();
            document.getElementById('executionOutput').textContent = data.result;
        } catch (error) {
            console.error('Error:', error);
        }
    });

    // Fix Code button
    document.getElementById('fixCodeBtn').addEventListener('click', async () => {
        const code = codeOutput.getValue();
        try {
            const response = await fetch('/fix', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ code })
            });
            const data = await response.json();
            codeOutput.setValue(data.fixed_code);
        } catch (error) {
            console.error('Error:', error);
        }
    });

    // Install Package button
    document.getElementById('installPackageBtn').addEventListener('click', async () => {
        const package = document.getElementById('packageInput').value;
        try {
            const response = await fetch('/install_package', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ package })
            });
            const data = await response.json();
            document.getElementById('executionOutput').textContent = data.result;
        } catch (error) {
            console.error('Error:', error);
        }
    });

    // Save button
    document.getElementById('saveBtn').addEventListener('click', async () => {
        const code = codeOutput.getValue();
        try {
            const response = await fetch('/save_code', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ code })
            });
            const data = await response.json();
            document.getElementById('executionOutput').textContent = data.result;
        } catch (error) {
            console.error('Error:', error);
        }
    });

    // Edit button
    document.getElementById('editBtn').addEventListener('click', () => {
        codeOutput.setOption('readOnly', false);
    });

    // Display Code checkbox
    document.getElementById('displayCodeCheckbox').addEventListener('change', function() {
        document.getElementById('codeOutput').style.display = this.checked ? 'block' : 'none';
    });
});
