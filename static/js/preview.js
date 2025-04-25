document.addEventListener('DOMContentLoaded', () => {
    console.log("Preview window loaded.");

    // --- DOM Elements ---
    const player = document.getElementById('previewPlayer');
    const subtitleDiv = document.getElementById('previewSubtitle');
    const thumbnailImg = document.getElementById('previewThumbnail');
    const sceneIdSpan = document.getElementById('previewSceneId');
    const startSpan = document.getElementById('previewStart');
    const endSpan = document.getElementById('previewEnd');
    const tagSpan = document.getElementById('previewTag');
    const descriptionP = document.getElementById('previewDescription');

    // --- State Variables ---
    let currentVideoId = null;
    let playEndTime = null; // For PLAY_SCENE mode
    let playEndInterval = null;
    let transcriptions = []; // Store transcriptions for subtitle display
    let scenes = [];         // Store scenes for info display

    // --- Constants ---
    const API_BASE_URL = 'http://localhost:5000/api'; // Must match app.js

    // --- Helper Functions ---
    function timecodeToSeconds(timecode) { // Reuse from app.js if possible, or redefine
        if (!timecode) return 0;
        const parts = timecode.split(':');
        if (parts.length !== 4) return 0;
        try {
            const hours = parseInt(parts[0], 10);
            const minutes = parseInt(parts[1], 10);
            const seconds = parseInt(parts[2], 10);
            const frames = parseInt(parts[3], 10);
            return hours * 3600 + minutes * 60 + seconds + frames / 30; // Assume 30fps
        } catch (e) { return 0; }
    }
    
    // --- Message Handling ---
    function sendMessageToOpener(message) {
        if (window.opener && !window.opener.closed) {
            // Send message back to the window that opened this one
            window.opener.postMessage(message, window.location.origin);
        } else {
            console.warn("Opener window not available.");
        }
    }

    window.addEventListener('message', (event) => {
        // Security: Check origin
        if (event.origin !== window.location.origin) {
            console.warn("Message received from unexpected origin:", event.origin);
            return;
        }

        const message = event.data;
        console.log("Message received in preview:", message); // Debug

        switch (message.type) {
            case 'LOAD_VIDEO':
                loadVideo(message.payload.videoId);
                break;
            case 'PLAY_SCENE':
                playScene(message.payload.start, message.payload.end, message.payload.sceneId);
                break;
            case 'SEEK_PLAY':
                seekAndPlay(message.payload.time);
                break;
            case 'RESET':
                resetPreview();
                break;
            default:
                console.warn("Unknown message type received:", message.type);
        }
    });

    // --- Core Functionality ---
    async function loadVideo(videoId) {
        console.log("Loading video:", videoId);
        if (!videoId || videoId === currentVideoId) return; // Avoid redundant loading

        currentVideoId = videoId;
        resetPreview(); // Clear previous state

        player.src = `${API_BASE_URL}/stream/${videoId}`;
        player.load(); // Start loading the video

        // Fetch scene and transcription data for this video
        try {
            const [scenesRes, transRes] = await Promise.all([
                fetch(`${API_BASE_URL}/scenes/${videoId}`),
                fetch(`${API_BASE_URL}/transcriptions/${videoId}`)
            ]);
            if (!scenesRes.ok) throw new Error(`Failed to fetch scenes: ${scenesRes.status}`);
            if (!transRes.ok) throw new Error(`Failed to fetch transcriptions: ${transRes.status}`);
            
            scenes = await scenesRes.json();
            transcriptions = await transRes.json();
            console.log(`Loaded ${scenes.length} scenes and ${transcriptions.length} transcriptions.`);
            // Optionally update UI with first scene info or wait for PLAY command
             if (scenes.length > 0) updateSceneInfoUI(scenes[0]);

        } catch (error) {
            console.error("Error loading video metadata:", error);
            scenes = [];
            transcriptions = [];
            // Display error to user?
        }
    }

    function playScene(startTime, endTime, sceneId) {
        console.log(`Playing scene ${sceneId} from ${startTime} to ${endTime}`);
        clearPlayEndCheck(); // Clear previous end check
        
        player.currentTime = startTime;
        player.play();
        playEndTime = endTime;

        // Update UI with current scene info
        const sceneData = scenes.find(s => s.id === sceneId);
        if (sceneData) updateSceneInfoUI(sceneData);

        // Set interval to check if playback reached the end time
        playEndInterval = setInterval(() => {
            if (player.currentTime >= playEndTime) {
                console.log(`Scene ${sceneId} playback ended.`);
                player.pause();
                clearPlayEndCheck();
                // Notify opener that playback ended for this scene
                sendMessageToOpener({ type: 'PLAYBACK_ENDED' });
            }
        }, 100); // Check every 100ms
    }

    function seekAndPlay(time) {
        console.log(`Seeking to ${time} and playing.`);
        clearPlayEndCheck(); // Stop scene-specific end check
        player.currentTime = time;
        player.play();
        // Find and update scene info for the seeked time
        updateSceneInfoForTime(time);
    }

    function resetPreview() {
        console.log("Resetting preview window.");
        player.pause();
        player.removeAttribute('src');
        player.load();
        clearPlayEndCheck();
        clearSceneInfoUI();
        clearSubtitle();
        scenes = [];
        transcriptions = [];
    }

    function clearPlayEndCheck() {
        if (playEndInterval) {
            clearInterval(playEndInterval);
            playEndInterval = null;
            playEndTime = null;
        }
    }

    // --- UI Update Functions ---
    function updateSceneInfoUI(sceneData) {
        if (!sceneData) {
            clearSceneInfoUI();
            return;
        }
        thumbnailImg.src = sceneData.thumbnail_path ? `${API_BASE_URL}/thumbnails/${sceneData.id}` : '/placeholder.jpg';
        sceneIdSpan.textContent = sceneData.scene_id || '-';
        startSpan.textContent = sceneData.start_timecode || '-';
        endSpan.textContent = sceneData.end_timecode || '-';
        tagSpan.textContent = sceneData.scene_evaluation_tag || '-';
        descriptionP.textContent = sceneData.description || '-';
    }
    
    function clearSceneInfoUI() {
        thumbnailImg.src = '/placeholder.jpg';
        sceneIdSpan.textContent = '-';
        startSpan.textContent = '-';
        endSpan.textContent = '-';
        tagSpan.textContent = '-';
        descriptionP.textContent = '-';
    }

     function updateSceneInfoForTime(currentTime) {
         const currentScene = scenes.find(scene => {
             const start = timecodeToSeconds(scene.start_timecode);
             const end = timecodeToSeconds(scene.end_timecode);
             return currentTime >= start && currentTime < end;
         });
         updateSceneInfoUI(currentScene); // Will clear if no scene found
     }

    function updateSubtitle(currentTime) {
        if (transcriptions.length === 0) {
             clearSubtitle();
            return;
        }
        const currentTrans = transcriptions.find(t => {
            const start = timecodeToSeconds(t.start_timecode);
            const end = timecodeToSeconds(t.end_timecode);
            return currentTime >= start && currentTime < end;
        });

        if (currentTrans && currentTrans.transcription) {
            subtitleDiv.textContent = currentTrans.transcription;
            subtitleDiv.classList.add('visible');
        } else {
            clearSubtitle();
        }
    }

    function clearSubtitle() {
        subtitleDiv.textContent = '';
        subtitleDiv.classList.remove('visible');
    }

    // --- Player Event Listeners ---
    player.addEventListener('timeupdate', () => {
        // Send current time back to opener window
        sendMessageToOpener({ type: 'TIME_UPDATE', payload: { currentTime: player.currentTime } });
        // Update subtitle based on current time
        updateSubtitle(player.currentTime);
        // Update scene info display based on current time (if not in scene-play mode)
        if (!playEndTime) { 
             updateSceneInfoForTime(player.currentTime);
        }
    });

    player.addEventListener('pause', () => {
        // When paused manually, stop the end check interval if it's running
        clearPlayEndCheck();
    });
    player.addEventListener('seeked', () => {
         // When seeked manually, stop the end check interval if it's running
         clearPlayEndCheck();
         updateSceneInfoForTime(player.currentTime);
         updateSubtitle(player.currentTime);
     });

    // --- Initialization ---
    // Get video ID from URL parameter
    const urlParams = new URLSearchParams(window.location.search);
    const initialVideoId = urlParams.get('videoId');

    if (initialVideoId) {
        loadVideo(initialVideoId);
    } else {
        console.warn("No videoId found in URL parameters.");
        // Optionally display a message in the preview window
    }

    // Notify the opener window that the preview window is ready
    sendMessageToOpener({ type: 'PREVIEW_READY' });

}); 