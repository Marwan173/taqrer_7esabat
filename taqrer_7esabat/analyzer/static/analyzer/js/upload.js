// Handle drag-and-drop file upload with progress
document.addEventListener('DOMContentLoaded', function() {
    const dropzone = document.getElementById('dropzone');
    const fileInput = document.getElementById('file-input');
    const uploadForm = document.getElementById('upload-form');
    const progressContainer = document.getElementById('progress-container');
    const progressBar = document.getElementById('progress-bar');
    const progressText = document.getElementById('progress-text');
    const errorContainer = document.getElementById('error-container');
    const loadingOverlay = document.getElementById('loading-overlay');
    
    if (!dropzone) return;
    
    // Drag and drop events
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropzone.addEventListener(eventName, preventDefaults);
    });
    
    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }
    
    ['dragenter', 'dragover'].forEach(eventName => {
        dropzone.addEventListener(eventName, () => dropzone.classList.add('dragover'));
    });
    
    ['dragleave', 'drop'].forEach(eventName => {
        dropzone.addEventListener(eventName, () => dropzone.classList.remove('dragover'));
    });
    
    // Handle drop
    dropzone.addEventListener('drop', function(e) {
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            handleFile(files[0]);
        }
    });
    
    // Handle click to select
    dropzone.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', function() {
        if (this.files.length > 0) {
            handleFile(this.files[0]);
        }
    });
    
    function handleFile(file) {
        // Validate file type
        const validTypes = ['.xlsx', '.xls',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'application/vnd.ms-excel'];
        const ext = '.' + file.name.split('.').pop().toLowerCase();
        
        if (!validTypes.includes(ext) && !validTypes.includes(file.type)) {
            showError('صيغة الملف غير مدعومة. يرجى رفع ملف بصيغة .xlsx أو .xls');
            return;
        }
        
        // Validate size (50MB)
        if (file.size > 52428800) {
            showError('حجم الملف كبير جداً. الحد الأقصى هو 50 ميجابايت');
            return;
        }
        
        uploadFile(file);
    }
    
    function uploadFile(file) {
        const formData = new FormData();
        formData.append('file', file);
        
        // Get CSRF token
        const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
        formData.append('csrfmiddlewaretoken', csrfToken);
        
        // Show progress
        hideError();
        progressContainer.style.display = 'block';
        dropzone.style.display = 'none';
        
        const xhr = new XMLHttpRequest();
        
        xhr.upload.addEventListener('progress', function(e) {
            if (e.lengthComputable) {
                const pct = Math.round((e.loaded / e.total) * 100);
                progressBar.style.width = pct + '%';
                progressBar.setAttribute('aria-valuenow', pct);
                if (pct < 100) {
                    progressText.textContent = `جاري رفع الملف... ${pct}%`;
                } else {
                    progressText.textContent = 'جاري تحليل البيانات...';
                    loadingOverlay.classList.add('active');
                }
            }
        });
        
        xhr.addEventListener('load', function() {
            loadingOverlay.classList.remove('active');
            if (xhr.status === 200) {
                try {
                    const response = JSON.parse(xhr.responseText);
                    if (response.success) {
                        window.location.href = response.redirect_url;
                    } else {
                        showError(response.error || 'حدث خطأ أثناء تحليل الملف');
                        resetUpload();
                    }
                } catch(e) {
                    // Non-JSON response (redirect)
                    window.location.reload();
                }
            } else {
                showError('حدث خطأ في الخادم. يرجى المحاولة مرة أخرى');
                resetUpload();
            }
        });
        
        xhr.addEventListener('error', function() {
            loadingOverlay.classList.remove('active');
            showError('فشل الاتصال بالخادم. تحقق من اتصال الإنترنت');
            resetUpload();
        });
        
        xhr.open('POST', uploadForm.action);
        xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');
        xhr.send(formData);
    }
    
    function showError(message) {
        errorContainer.textContent = message;
        errorContainer.style.display = 'block';
    }
    
    function hideError() {
        errorContainer.style.display = 'none';
    }
    
    function resetUpload() {
        progressContainer.style.display = 'none';
        dropzone.style.display = 'flex';
        progressBar.style.width = '0%';
    }
});
