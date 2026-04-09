document.addEventListener('DOMContentLoaded', () => {
    // REAL API ENDPOINT
    const API_URL = 'https://qchvm99sfh.execute-api.us-east-1.amazonaws.com';

    // DOM Elements
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    const browseBtn = document.getElementById('browse-btn');
    const analysisPanel = document.getElementById('analysis-panel');
    const fileNameDisplay = document.getElementById('file-name-display');
    const removeFileBtn = document.getElementById('remove-file-btn');
    const analyzeBtn = document.getElementById('analyze-btn');
    const btnText = analyzeBtn.querySelector('.btn-text');
    const loader = analyzeBtn.querySelector('.loader');
    const resultsPanel = document.getElementById('results-panel');
    const uploadSection = document.querySelector('.upload-section');
    const resetBtn = document.getElementById('reset-btn');
    
    // Architecture pipeline steps
    const steps = [
        document.getElementById('step-s3'),
        document.getElementById('step-textract'),
        document.getElementById('step-comprehend'),
        document.getElementById('step-db')
    ];
    const connectors = document.querySelectorAll('.step-connector');

    let currentFile = null;

    // --- File Upload Handling ---

    browseBtn.addEventListener('click', (e) => {
        e.preventDefault();
        fileInput.click();
    });

    dropZone.addEventListener('click', (e) => {
        if(e.target !== browseBtn) {
            fileInput.click();
        }
    });

    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, preventDefaults, false);
    });

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, () => {
            dropZone.classList.add('dragover');
        }, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, () => {
            dropZone.classList.remove('dragover');
        }, false);
    });

    dropZone.addEventListener('drop', (e) => {
        const dt = e.dataTransfer;
        handleFiles(dt.files);
    });

    fileInput.addEventListener('change', function() {
        handleFiles(this.files);
    });

    function handleFiles(files) {
        if (files.length > 0) {
            currentFile = files[0];
            
            const validTypes = ['image/jpeg', 'image/png'];
            if (!validTypes.includes(currentFile.type)) {
                alert('Please upload a JPG or PNG file (Synchronous Textract required constraint).');
                return;
            }

            fileNameDisplay.textContent = currentFile.name;
            dropZone.classList.add('hidden');
            analysisPanel.classList.remove('hidden');
        }
    }

    removeFileBtn.addEventListener('click', () => {
        currentFile = null;
        fileInput.value = '';
        dropZone.classList.remove('hidden');
        analysisPanel.classList.add('hidden');
        resetPipeline();
    });

    // --- Serverless Architecture REAL Integration ---

    analyzeBtn.addEventListener('click', async () => {
        if (!currentFile) return;

        // Start UI state
        analyzeBtn.disabled = true;
        btnText.textContent = 'Processing...';
        loader.classList.remove('hidden');

        try {
            // STEP 1: Get presigned URL and Upload to S3
            setStepActive(0, 'Requesting Upload URL...');
            const urlResult = await fetch(`${API_URL}/get-upload-url?filename=${encodeURIComponent(currentFile.name)}&type=${encodeURIComponent(currentFile.type)}`);
            const urlData = await urlResult.json();
            
            if(!urlResult.ok) throw new Error(urlData.error || "Failed to get upload URL");

            btnText.textContent = 'Uploading to S3...';
            const uploadResult = await fetch(urlData.uploadUrl, {
                method: 'PUT',
                body: currentFile,
                headers: { 'Content-Type': currentFile.type }
            });
            
            if(!uploadResult.ok) throw new Error("Failed to upload to S3");
            completeStep(0);

            // STEP 2: Textract processing (starts the /analyze request)
            setStepActive(1, 'AWS Textract Processing...');
            
            const analyzeReq = fetch(`${API_URL}/analyze`, {
                method: 'POST',
                body: JSON.stringify({ key: urlData.key }),
                headers: { 'Content-Type': 'application/json' }
            });

            // Simulate UI progressing through Comprehend and DB while we wait for POST 
            setTimeout(() => { completeStep(1); setStepActive(2, 'Comprehend Analysis...'); }, 2500);
            
            const analyzeResult = await analyzeReq;
            const data = await analyzeResult.json();

            if(!analyzeResult.ok) throw new Error(data.error || "Failed to analyze document");

            completeStep(2);
            setStepActive(3, 'Saving to DynamoDB...');
            setTimeout(() => completeStep(3), 500);

            setTimeout(() => {
                btnText.textContent = 'Analysis Complete';
                loader.classList.add('hidden');
                showResults(data);
            }, 1000);

        } catch(err) {
            console.error('Full Pipeline Error Detail:', err);
            alert('Pipeline Error: ' + err.message + '\nCheck console for details.');
            resetPipeline();
        }
    });

    function setStepActive(index, text) {
        steps[index].classList.add('active');
        btnText.textContent = text;
    }

    function completeStep(index) {
        steps[index].classList.remove('active');
        steps[index].classList.add('completed');
        if (index < connectors.length) {
            connectors[index].classList.add('completed');
        }
    }

    function resetPipeline() {
        steps.forEach(step => {
            step.classList.remove('active', 'completed');
        });
        connectors.forEach(conn => {
            conn.classList.remove('completed');
        });
        analyzeBtn.disabled = false;
        btnText.textContent = 'Start Analysis Pipeline';
        loader.classList.add('hidden');
    }

    function showResults(data) {
        uploadSection.classList.add('hidden');
        resultsPanel.classList.remove('hidden');

        const mockResultsContainer = document.getElementById('mock-results-content');
        
        let markersHtml = '';
        if(data.markers && data.markers.length > 0) {
            data.markers.forEach(m => {
                const statusClass = `status-${m.status.toLowerCase()}`;
                markersHtml += `
                 <div class="mock-data-row">
                    <div class="marker-info">
                        <span class="mock-label">${m.name}</span>
                        <span class="ref-range">Range: ${m.range} ${m.unit}</span>
                    </div>
                    <div class="marker-value">
                        <span class="mock-value ${statusClass}">${m.value} ${m.unit}</span>
                        <span class="status-tag ${statusClass}">${m.status}</span>
                    </div>
                 </div>`;
            });
        } else {
            markersHtml = `
                <div class="no-markers">
                    <p style="color:var(--text-muted); margin-bottom: 10px;">No clinical markers were automatically identified.</p>
                    <div class="raw-preview">
                        <strong>Extracted Text Preview:</strong>
                        <p>${data.rawTextPreview || 'No text found'}</p>
                    </div>
                </div>`;
        }

        mockResultsContainer.innerHTML = `
            <div class="mock-data-row header-row">
                <span class="mock-label">Analysis Result</span>
                <span class="mock-value">${data.sentiment === 'POSITIVE' ? 'Overall Normal' : 'Requires Review'}</span>
            </div>
            <div class="markers-container">
                ${markersHtml}
            </div>
        `;
    }

    resetBtn.addEventListener('click', () => {
        resultsPanel.classList.add('hidden');
        uploadSection.classList.remove('hidden');
        
        currentFile = null;
        fileInput.value = '';
        dropZone.classList.remove('hidden');
        analysisPanel.classList.add('hidden');
        resetPipeline();
    });
});
