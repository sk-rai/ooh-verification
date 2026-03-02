let currentScreen = 1;
let campaignCode = '';
let stream = null;

function showScreen(screenNumber) {
    const screens = document.querySelectorAll('.screen');
    screens.forEach((screen, index) => {
        if (index + 1 === screenNumber) {
            screen.classList.add('active');
            screen.classList.remove('exit-left');
        } else if (index + 1 < screenNumber) {
            screen.classList.add('exit-left');
            screen.classList.remove('active');
        } else {
            screen.classList.remove('active', 'exit-left');
        }
    });
    currentScreen = screenNumber;
}

function startVerification() {
    const input = document.getElementById('campaignCode');
    campaignCode = input.value.trim();
    
    if (!campaignCode) {
        input.style.borderColor = '#f44336';
        input.placeholder = 'Campaign code required';
        return;
    }
    
    showScreen(2);
    initCamera();
}

async function initCamera() {
    try {
        // Try to access rear camera (environment facing)
        stream = await navigator.mediaDevices.getUserMedia({ 
            video: { 
                facingMode: { exact: 'environment' }
            } 
        });
        const video = document.getElementById('video');
        video.srcObject = stream;
    } catch (err) {
        console.log('Camera not available, using placeholder');
        // Show placeholder for demo
        const preview = document.getElementById('cameraPreview');
        preview.innerHTML = `
            <div style="width: 100%; height: 100%; display: flex; align-items: center; justify-content: center; flex-direction: column; color: #fff; padding: 20px; text-align: center;">
                <svg width="80" height="80" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"></path>
                    <circle cx="12" cy="13" r="4"></circle>
                </svg>
                <p style="margin-top: 16px; font-size: 14px; opacity: 0.8;">Camera preview<br>(Demo mode)</p>
            </div>
        `;
    }
}

function capturePhoto() {
    const video = document.getElementById('video');
    const canvas = document.getElementById('canvas');
    
    if (stream) {
        // Real camera capture
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        const ctx = canvas.getContext('2d');
        ctx.drawImage(video, 0, 0);
        
        const capturedPhoto = document.getElementById('capturedPhoto');
        capturedPhoto.src = canvas.toDataURL('image/jpeg');
        
        // Stop camera
        stream.getTracks().forEach(track => track.stop());
    } else {
        // Demo mode - use placeholder
        const capturedPhoto = document.getElementById('capturedPhoto');
        capturedPhoto.src = 'data:image/svg+xml,' + encodeURIComponent(`
            <svg width="400" height="600" xmlns="http://www.w3.org/2000/svg">
                <rect width="400" height="600" fill="#c0c0c0"/>
                <text x="200" y="280" font-family="Arial" font-size="24" fill="#666" text-anchor="middle">Photo Area</text>
                <text x="200" y="320" font-family="Arial" font-size="16" fill="#888" text-anchor="middle">Billboard Image</text>
            </svg>
        `);
    }
    
    // Get current location and time
    updateWatermark();
    showScreen(3);
}

function updateWatermark() {
    const now = new Date();
    const timestamp = now.toLocaleString('en-IN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        timeZone: 'Asia/Kolkata',
        timeZoneName: 'short'
    }).replace(',', '');
    
    document.getElementById('timestamp').textContent = timestamp;
    document.getElementById('campaignDisplay').textContent = `CAMPAIGN: ${campaignCode}`;
    
    // Try to get real GPS
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
            (position) => {
                const lat = position.coords.latitude.toFixed(4);
                const lon = position.coords.longitude.toFixed(4);
                const acc = position.coords.accuracy.toFixed(1);
                
                document.getElementById('gpsCoords').textContent = 
                    `${lat}°N, ${lon}°E`;
                document.getElementById('accuracy').textContent = `±${acc}m`;
            },
            () => {
                // Keep demo coordinates if GPS fails
                console.log('Using demo GPS coordinates');
            }
        );
    }
}

function retakePhoto() {
    showScreen(2);
    initCamera();
}

function submitPhoto() {
    // Simulate submission
    alert('✓ Photo submitted successfully!\n\nIn production, this would upload to your backend with tamper-proof verification.');
    
    // Reset to first screen
    showScreen(1);
    document.getElementById('campaignCode').value = '';
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    showScreen(1);
});
