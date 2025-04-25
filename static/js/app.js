$(document).ready(function() {
    console.log("Excel-like UI app.js loaded and DOM ready");

    // --- Global Variables ---
    let currentVideoId = null;
    let scenes = [];
    let transcriptions = [];
    let selectedScenes = new Set();
    let scenesTable = null;
    let transcriptionsTable = null;
    let currentScene = null;
    let playEndInterval = null;
    let playEndTime = null;
    let currentPlayQueue = null; // Added from previous version for popup playback queue
    let currentPlayIndex = 0;    // Added from previous version for popup playback queue

    // --- DOM Elements (using new IDs) ---
    const videoSelector = $('#video-selector');
    const openPlayerBtn = $('#open-player');
    const closePlayerBtn = $('#close-player-btn');
    const playerPopup = $('#video-player-popup');
    const popupOverlay = $('#popup-overlay');
    const popupPlayer = $('#popup-video-player')[0]; // Get the raw DOM element for video API
    const popupSubtitleDiv = $('#popup-subtitle-container');
    const popupThumbnailImg = $('#popup-scene-thumbnail');
    const popupSceneIdSpan = $('#popup-scene-id');
    const popupStartSpan = $('#popup-scene-start');
    const popupEndSpan = $('#popup-scene-end');
    const popupTagSpan = $('#popup-scene-tag');
    const popupDescriptionP = $('#popup-scene-description');

    const tagFilter = $('#tag-filter');
    const qualityFilter = $('#quality-filter');
    const resetFiltersBtn = $('#reset-filters');
    const selectAllScenesBtn = $('#select-all-scenes-btn');
    const deselectAllScenesBtn = $('#deselect-all-scenes-btn');
    const playSelectedScenesBtn = $('#play-selected-scenes-btn');
    const exportEDLBtn = $('#export-edl-btn');
    const exportSRTBtn = $('#export-srt-btn');
    const selectedCountDisplay = $('#selected-count-display');
    const selectedDurationDisplay = $('#selected-duration-display');
    const selectAllCheckbox = $('#select-all-scenes-checkbox');

    // --- Constants ---
    const API_BASE_URL = 'http://localhost:5000/api';

    // --- Helper Functions ---
    function timecodeToSeconds(timecode) {
        if (!timecode) return 0;
        const parts = timecode.split(':');
        if (parts.length !== 4) return 0;
        try {
            const hours = parseInt(parts[0], 10);
            const minutes = parseInt(parts[1], 10);
            const seconds = parseInt(parts[2], 10);
            const frames = parseInt(parts[3], 10);
            const frameRate = 30; // Assume 30fps, adjust if needed
            return hours * 3600 + minutes * 60 + seconds + frames / frameRate;
        } catch (e) {
            console.error("Error parsing timecode:", timecode, e);
            return 0;
        }
    }

    function secondsToTimecode(totalSeconds) {
        if (isNaN(totalSeconds) || totalSeconds < 0) return "00:00:00:00";
        const frameRate = 30; // Assume 30fps
        const hours = Math.floor(totalSeconds / 3600);
        const minutes = Math.floor((totalSeconds % 3600) / 60);
        const seconds = Math.floor(totalSeconds % 60);
        const frames = Math.floor((totalSeconds - Math.floor(totalSeconds)) * frameRate);
        
        return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}:${String(frames).padStart(2, '0')}`;
    }

    function updateSceneSelection(sceneId, isSelected) {
        if (isSelected) {
            selectedScenes.add(sceneId);
        } else {
            selectedScenes.delete(sceneId);
        }
        updateSelectedStats();
        updateSelectAllCheckboxState();
        updateButtonStates(); // Update button states based on selection
    }

    function updateSelectedStats() {
        const count = selectedScenes.size;
        let totalDuration = 0;
        let visibleAndSelectedCount = 0;
        let visibleAndSelectedDuration = 0;

        // Calculate total duration for all selected scenes
        scenes.forEach(scene => {
            if (selectedScenes.has(scene.id)) {
                const start = timecodeToSeconds(scene.start_timecode);
                const end = timecodeToSeconds(scene.end_timecode);
                if (!isNaN(start) && !isNaN(end) && end >= start) {
                    totalDuration += (end - start);
                }
            }
        });

        // Calculate stats for visible selected scenes if table exists
        if (scenesTable && scenesTable.rows) {
            scenesTable.rows({ search: 'applied' }).every(function() {
                const data = this.data();
                if (data && selectedScenes.has(data.id)) {
                    visibleAndSelectedCount++;
                    // Duration calculation for visible can be added if needed
                }
            });
        } else {
             // If table not ready, use total count for visible count initially
             visibleAndSelectedCount = count;
        }


        // Update UI
        selectedCountDisplay.text(`${visibleAndSelectedCount} / ${count}`);
        selectedDurationDisplay.text(secondsToTimecode(totalDuration));
    }

    function updateSelectAllCheckboxState() {
        if (!scenesTable || !selectAllCheckbox.length) return;

        const totalVisibleRows = scenesTable.rows({ search: 'applied' }).count();
        let selectedVisibleRows = 0;
        scenesTable.rows({ search: 'applied' }).every(function() {
            const data = this.data();
            if (data && selectedScenes.has(data.id)) {
                selectedVisibleRows++;
            }
        });

        if (totalVisibleRows === 0) {
            selectAllCheckbox.prop('checked', false).prop('indeterminate', false);
        } else if (selectedVisibleRows === 0) {
            selectAllCheckbox.prop('checked', false).prop('indeterminate', false);
        } else if (selectedVisibleRows === totalVisibleRows) {
            selectAllCheckbox.prop('checked', true).prop('indeterminate', false);
        } else {
            selectAllCheckbox.prop('checked', false).prop('indeterminate', true);
        }
    }

    // Renamed from updateExportButtonStates to be more general
    function updateButtonStates() {
        const hasSelection = selectedScenes.size > 0;
        exportEDLBtn.prop('disabled', !hasSelection).toggleClass('disabled', !hasSelection);
        exportSRTBtn.prop('disabled', !hasSelection).toggleClass('disabled', !hasSelection);
        playSelectedScenesBtn.prop('disabled', !hasSelection).toggleClass('disabled', !hasSelection);
        // Disable open player if no video selected
        openPlayerBtn.prop('disabled', !currentVideoId).toggleClass('disabled', !currentVideoId);
    }

    function showLoadingIndicator(show) {
        console.log(`Loading: ${show}`);
        $('body').toggleClass('loading', show); // Add/remove 'loading' class to body
        // Add more sophisticated indicator logic here if needed
    }

    function findSceneDataByTime(currentTime) {
         return scenes.find(scene => {
            const start = timecodeToSeconds(scene.start_timecode);
            const end = timecodeToSeconds(scene.end_timecode);
            return currentTime >= start && currentTime < end;
        });
    }

    function downloadFile(blob, filename) {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url; a.download = filename;
        document.body.appendChild(a);
        a.click();
        setTimeout(() => { document.body.removeChild(a); URL.revokeObjectURL(url); }, 200);
    }

    function handleExportError(fileType) {
        return function(error) {
            console.error(`${fileType} エクスポートエラー:`, error);
            alert(`${fileType}ファイルのエクスポートに失敗しました: ${error.message}`);
        }
    }

    async function handleExportResponse(response) {
        if (!response.ok) {
            try {
                const errData = await response.json();
                throw new Error(`HTTP error! status: ${response.status}, message: ${errData.error || 'Unknown error'}`);
            } catch (jsonError) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
        }
        const contentDisposition = response.headers.get('content-disposition');
        let filename = `exported_file`;
        if (contentDisposition) {
            const filenameMatch = contentDisposition.match(/filename="?(.+?)"?$/);
            if (filenameMatch && filenameMatch.length > 1) { filename = filenameMatch[1]; }
        }
        const blob = await response.blob();
        downloadFile(blob, filename);
    }

    // --- Main Application Functions ---

    // --- Data Loading ---
    async function loadVideos() {
        try {
            console.log("Fetching videos...");
            const response = await fetch(`${API_BASE_URL}/videos`);
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            const videosData = await response.json();
            console.log(`Fetched ${videosData.length} videos.`);
            
            if (videoSelector.length === 0) {
                console.error("Error: #video-selector element not found!");
                return;
            }
            
            videoSelector.empty().append('<option value="">動画を選択...</option>');
            videosData.forEach(video => {
                const durationText = video.duration_seconds ? ` (${video.duration_seconds.toFixed(1)}s)` : '';
                const option = $('<option></option>')
                                .val(video.id)
                                .text(`${video.filename}${durationText}`);
                videoSelector.append(option);
            });
        } catch (error) {
            console.error('動画一覧の取得に失敗しました:', error);
            alert('動画一覧の取得に失敗しました。');
        }
    }

    async function loadVideoData(videoId) {
        if (!videoId) {
             // Reset UI if no video is selected
             currentVideoId = null;
             scenes = [];
             transcriptions = [];
             selectedScenes.clear();
             if (scenesTable) scenesTable.clear().draw();
             if (transcriptionsTable) transcriptionsTable.clear().draw();
             updateSelectedStats();
             updateButtonStates();
             updateSelectAllCheckboxState();
             resetPlayer(); // Close and reset player
             console.log("Video deselected. UI Reset.");
             return;
        }
        console.log(`Loading data for video ID: ${videoId}`);
        currentVideoId = videoId;
        showLoadingIndicator(true);
        try {
            const [scenesRes, transRes] = await Promise.all([
                fetch(`${API_BASE_URL}/scenes/${videoId}`),
                fetch(`${API_BASE_URL}/transcriptions/${videoId}`)
            ]);
            if (!scenesRes.ok) throw new Error(`Scenes fetch failed: ${scenesRes.status}`);
            if (!transRes.ok) throw new Error(`Transcriptions fetch failed: ${transRes.status}`);

            scenes = await scenesRes.json();
            transcriptions = await transRes.json();
            console.log(`Loaded ${scenes.length} scenes, ${transcriptions.length} transcriptions.`);

            // Populate DataTables
            if (scenesTable) scenesTable.clear().rows.add(scenes).draw();
            if (transcriptionsTable) transcriptionsTable.clear().rows.add(transcriptions).draw();

            // Reset selections and update UI
            selectedScenes.clear();
            updateSelectedStats();
            updateButtonStates();
            updateSelectAllCheckboxState();
            resetPlayer(); // Reset player if it was open

        } catch (error) {
            console.error('Error loading video data:', error);
            alert('シーンまたは字幕データの読み込みに失敗しました。');
            // Clear tables on error
            if (scenesTable) scenesTable.clear().draw();
            if (transcriptionsTable) transcriptionsTable.clear().draw();
        } finally {
            showLoadingIndicator(false);
        }
    }

    // --- DataTables Initialization ---
    function initTables() {
        console.log("Initializing DataTables...");
        try {
            // Destroy existing tables if they exist to prevent reinitialization errors
            if ($.fn.DataTable.isDataTable('#scenes-table')) {
                 $('#scenes-table').DataTable().destroy();
            }
             if ($.fn.DataTable.isDataTable('#transcriptions-table')) {
                 $('#transcriptions-table').DataTable().destroy();
            }

            scenesTable = $('#scenes-table').DataTable({
                // data: [], // Initialize with empty data, loaded later
                columns: [
                    { data: null, orderable: false, className: 'select-checkbox dt-body-center', defaultContent: '', width: '1%' }, // Checkbox
                    { data: 'id', title: 'サムネイル', orderable: false, className: 'thumbnail-cell dt-body-center', // Thumbnail
                        render: function(data, type, row) {
                            // Use placeholder if thumbnail path is missing
                            const imgSrc = row.thumbnail_path ? `${API_BASE_URL}/thumbnails/${data}` : 'placeholder.jpg';
                            return `<img src="${imgSrc}" alt="Scene ${row.scene_id || ''}" loading="lazy" style="max-height: 30px; cursor: pointer;">`; // Added cursor pointer
                        }
                     },
                    { data: 'scene_id', title: 'Scene#' },
                    { data: 'filename', title: 'ファイル名', defaultContent: '-' }, // Placeholder - needs backend data
                    { data: 'start_timecode', title: '開始' },
                    { data: 'end_timecode', title: '終了' },
                    { data: null, title: '長さ', // Calculated duration
                        render: function(data, type, row) {
                            const start = timecodeToSeconds(row.start_timecode);
                            const end = timecodeToSeconds(row.end_timecode);
                            return (end > start) ? (end - start).toFixed(2) + 's' : '-';
                        }
                     },
                    { data: 'description', title: '説明', className: 'description-cell', defaultContent: '-' },
                    { data: 'scene_evaluation_tag', title: '評価タグ', defaultContent: '-' },
                    { data: 'scene_good_reason', title: '良い理由', defaultContent: '-' },
                    { data: 'scene_bad_reason', title: '悪い理由', defaultContent: '-' },
                    { data: null, title: 'アクション', orderable: false, className: 'action-cell dt-body-center', // Action
                        render: function(data, type, row) {
                             const startTime = timecodeToSeconds(row.start_timecode);
                             return `<button class="action-button scene-play-btn" data-start-time="${startTime}" title="このシーンを再生"><i class="fas fa-play"></i></button>`;
                        }
                     }
                ],
                order: [[4, 'asc']], // Sort by Start timecode
                scrollY: 'calc(100vh - 300px)', // Adjust based on actual layout height
                scrollCollapse: true,
                paging: false,
                info: false,
                searching: true, // Enable DataTables search box
                autoWidth: false,
                // fixedHeader: true, // Consider enabling for better UX
                // responsive: true, // Consider enabling for smaller screens
                columnDefs: [
                    { // Checkbox column rendering
                        targets: 0,
                        searchable: false,
                        orderable: false,
                        render: function (data, type, row, meta){
                             const isChecked = selectedScenes.has(row.id);
                            return `<input type="checkbox" class="dt-checkbox" data-scene-id="${row.id}" ${isChecked ? 'checked' : ''}>`;
                        }
                    }
                ],
                // Language settings for search box etc.
                // language: { search: "_INPUT_", searchPlaceholder: "テーブル内を検索..." } 
            });

            transcriptionsTable = $('#transcriptions-table').DataTable({
                 // data: [], // Initialize empty
                 columns: [
                    { data: 'scene_id', title: 'Scene#' },
                    { data: 'filename', title: 'ファイル名', defaultContent: '-' }, // Placeholder
                    { data: 'start_timecode', title: '開始' },
                    { data: 'end_timecode', title: '終了' },
                    { data: 'transcription', title: '字幕テキスト', className: 'transcription-cell', defaultContent: '-' },
                    { data: 'transcription_good_reason', title: '良い理由', defaultContent: '-' },
                    { data: 'transcription_bad_reason', title: '悪い理由', defaultContent: '-' },
                    { data: null, title: 'アクション', orderable: false, className: 'action-cell dt-body-center', // Action
                        render: function(data, type, row) {
                             const startTime = timecodeToSeconds(row.start_timecode);
                             return `<button class="action-button transcription-play-btn" data-start-time="${startTime}" title="ここから再生"><i class="fas fa-play"></i></button>`;
                        }
                     }
                ],
                order: [[2, 'asc']], // Sort by Start timecode
                scrollY: 'calc(100vh - 300px)', // Adjust
                scrollCollapse: true,
                paging: false,
                info: false,
                searching: true,
                autoWidth: false,
                // responsive: true
                // language: { search: "_INPUT_", searchPlaceholder: "テーブル内を検索..." }
            });
             console.log('DataTables initialized successfully.');
        } catch(error) {
            console.error('Error initializing DataTables:', error);
            alert('テーブルの初期化に失敗しました。');
        }
    }

    // --- Event Listeners ---
    function initEventListeners() {
        console.log("Initializing event listeners...");

        // Video selection
        videoSelector.on('change', function() {
            loadVideoData($(this).val());
        });

        // Open/Close Player Popup
        openPlayerBtn.on('click', togglePlayerPopup);
        closePlayerBtn.on('click', togglePlayerPopup);
        popupOverlay.on('click', togglePlayerPopup);

        // Tab switching
        $('.tab-button').on('click', function() {
            const tabId = $(this).data('tab');
            $('.tab-button').removeClass('active');
            $(this).addClass('active');
            $('.tab-pane').removeClass('active');
            $(`#${tabId}-tab`).addClass('active');
            // Adjust DataTable column widths after tab switch for proper layout
            if (scenesTable) scenesTable.columns.adjust().draw(); // Use draw() to redraw if needed
            if (transcriptionsTable) transcriptionsTable.columns.adjust().draw();
        });

        // Filtering
        tagFilter.on('change', applyFilters);
        qualityFilter.on('change', applyFilters); // Needs mapping logic in applyFilters
        resetFiltersBtn.on('click', resetFilters);

        // Scene Selection Buttons
        selectAllCheckbox.on('change', handleSelectAllCheckbox);
        selectAllScenesBtn.on('click', selectAllVisibleScenes);
        deselectAllScenesBtn.on('click', deselectAllVisibleScenes);

        // --- DataTables Row Click/Checkbox Handling ---
        // Click on row (excluding checkbox, button, image) toggles checkbox
        $('#scenes-table tbody').on('click', 'tr', function(e) {
            if ($(e.target).is('input[type="checkbox"], button, i, img')) {
                return; // Ignore clicks on interactive elements within the row
            }
            const checkbox = $(this).find('input.dt-checkbox');
            if (checkbox.length) {
                checkbox.prop('checked', !checkbox.prop('checked')).trigger('change');
            }
        });
        // Handle checkbox change event itself (covers direct clicks and row clicks)
         $('#scenes-table tbody').on('change', 'input.dt-checkbox', function() {
            const sceneId = $(this).data('scene-id');
            const isChecked = $(this).prop('checked');
            updateSceneSelection(sceneId, isChecked);
        });

        // Play Buttons in Tables
        $('#scenes-table tbody').on('click', '.scene-play-btn', function(e) {
            e.stopPropagation(); // Prevent row click event
            const startTime = $(this).data('start-time');
            const sceneId = $(this).closest('tr').find('input.dt-checkbox').data('scene-id');
            const scene = scenes.find(s => s.id === sceneId);
             if (scene) {
                 openPlayerAndPlay(startTime, timecodeToSeconds(scene.end_timecode), scene); // Pass end time and scene data
             } else {
                 openPlayerAndPlay(startTime); // Seek only if scene data not found
             }
        });
         $('#transcriptions-table tbody').on('click', '.transcription-play-btn', function(e) {
            e.stopPropagation();
            const startTime = $(this).data('start-time');
            openPlayerAndPlay(startTime); // Seek only
        });

        // Thumbnail click in scenes table
        $('#scenes-table tbody').on('click', 'img', function(e) {
            e.stopPropagation();
            const sceneId = $(this).closest('tr').find('input.dt-checkbox').data('scene-id');
            const scene = scenes.find(s => s.id === sceneId);
            if (scene) {
                const startTime = timecodeToSeconds(scene.start_timecode);
                const endTime = timecodeToSeconds(scene.end_timecode);
                openPlayerAndPlay(startTime, endTime, scene);
            }
        });

        // Play Selected Scenes Button
        playSelectedScenesBtn.on('click', playSelectedScenesInPopup);

        // Export Buttons
        exportEDLBtn.on('click', exportEDL);
        exportSRTBtn.on('click', exportSRT);

        // Popup Video Player Events
        $(popupPlayer).on('timeupdate', handlePopupTimeUpdate);
        $(popupPlayer).on('pause ended', handlePopupPause); // Handle both pause and natural end
        $(popupPlayer).on('seeked', handlePopupSeeked);

        console.log("Event listeners initialized.");
    }

    // --- UI Interaction Functions ---
    function togglePlayerPopup() {
        if (!currentVideoId && !playerPopup.is(':visible')) { // Prevent opening if no video selected
            alert('動画を選択してください。');
            return;
        }
        const isVisible = playerPopup.is(':visible');
        if (isVisible) {
            playerPopup.hide();
            popupOverlay.hide();
            popupPlayer.pause(); // Pause video when closing
            resetPlayer(); // Also reset player state
        } else {
            // Load video source if not already set or changed
            const currentSrc = $(popupPlayer).find('source').attr('src');
            const expectedSrc = `${API_BASE_URL}/stream/${currentVideoId}`;
            if (!currentSrc || currentSrc !== expectedSrc) {
                console.log("Setting player source:", expectedSrc);
                $(popupPlayer).find('source').attr('src', expectedSrc);
                popupPlayer.load(); // Important to load the new source
            }
            playerPopup.show();
            popupOverlay.show();
            
            // ポップアップをドラッグ可能にする
            playerPopup.draggable({
                handle: '.popup-header', // ヘッダー部分をドラッグハンドルとして使用
                start: function() {
                    $(this).css('transform', 'none'); // ドラッグ開始時にtransformをリセット
                }
            }).resizable({
                minWidth: 400,
                minHeight: 300
            });
        }
    }
    
    function applyFilters() {
        const tag = tagFilter.val();
        // Assuming quality filter applies to transcription table's 'good/bad reason' or description?
        // This needs clarification on which column qualityFilter targets.
        // Example: Filter scene table by tag (column index 8)
        scenesTable.column(8).search(tag ? `^${tag}$` : '', true, false).draw();

        // Example: Filter transcription table (needs target column index)
        // const qualityTargetColumnIndex = 5; // Example: Good Reason column
        // transcriptionsTable.column(qualityTargetColumnIndex).search(qualityFilter.val() ? `^${qualityFilter.val()}$` : '', true, false).draw();
        
        updateSelectAllCheckboxState();
        updateSelectedStats(); // Update stats based on filtered view
    }

    function resetFilters() {
        tagFilter.val('');
        qualityFilter.val('');
        if (scenesTable) scenesTable.columns().search('').draw();
        if (transcriptionsTable) transcriptionsTable.columns().search('').draw();
        updateSelectAllCheckboxState();
        updateSelectedStats();
    }

    function handleSelectAllCheckbox() {
        const isChecked = $(this).prop('checked');
        // Select/deselect only visible rows based on checkbox state
        $('#scenes-table tbody tr').each(function() {
             const checkbox = $(this).find('input.dt-checkbox');
             if (checkbox.length) {
                  // Check if row is visible (DataTables adds display:none for filtered rows)
                  // This check might be complex, relying on DataTables API is better
                  // For simplicity, this selects all rendered checkboxes.
                  // A better approach uses scenesTable.rows({ search: 'applied' })
                  checkbox.prop('checked', isChecked).trigger('change');
             }
        });
        // A more robust way using DataTables API:
        /*
        const rowsToModify = scenesTable.rows({ search: 'applied' }).nodes().to$();
        rowsToModify.find('input.dt-checkbox').prop('checked', isChecked).trigger('change');
        */
    }
    
    function selectAllVisibleScenes() {
        scenesTable.rows({ search: 'applied' }).nodes().to$().find('input.dt-checkbox:not(:checked)').prop('checked', true).trigger('change');
        updateSelectAllCheckboxState(); // Ensure main checkbox reflects state
    }

    function deselectAllVisibleScenes() {
         scenesTable.rows({ search: 'applied' }).nodes().to$().find('input.dt-checkbox:checked').prop('checked', false).trigger('change');
         updateSelectAllCheckboxState(); // Ensure main checkbox reflects state
    }
    
    // --- Popup Player Functions ---
     function openPlayerAndPlay(startTime, endTime = null, sceneData = null) {
         if (!currentVideoId) {
             alert("動画が選択されていません。");
             return;
         }
         if (!playerPopup.is(':visible')) {
             togglePlayerPopup(); // Open popup if closed
         }
         
         // Ensure video source is correct
         const currentSrc = $(popupPlayer).find('source').attr('src');
         const expectedSrc = `${API_BASE_URL}/stream/${currentVideoId}`;
         
         const playLogic = () => seekAndPlayInPopup(startTime, endTime, sceneData);

         if (!currentSrc || currentSrc !== expectedSrc) {
             console.log("Setting player source for playback:", expectedSrc);
             $(popupPlayer).find('source').attr('src', expectedSrc);
             popupPlayer.load();
             // Wait for video to be ready before seeking and playing
             $(popupPlayer).off('canplay.playlogic').one('canplay.playlogic', playLogic);
         } else {
             // If source is already correct, play directly
             playLogic();
         }
     }

     function seekAndPlayInPopup(startTime, endTime = null, sceneData = null) {
         console.log(`Popup: Seek to ${startTime}, EndTime: ${endTime}`);
         clearPopupEndCheck(); // Clear any previous end check
         
         // Check if metadata is loaded before setting currentTime
         if (popupPlayer.readyState >= 1) { // HAVE_METADATA or higher
             popupPlayer.currentTime = startTime;
             popupPlayer.play().catch(e => console.error("Play error:", e)); // Play and catch potential errors
             playEndTime = endTime; // Store end time for scene playback

             // Update scene info in popup
             updatePopupSceneInfo(sceneData || findSceneDataByTime(startTime));

             // If playing a specific scene (endTime is set), set up interval to check for end
             if (playEndTime !== null && playEndTime > startTime) {
                 playEndInterval = setInterval(() => {
                     if (!popupPlayer.paused && popupPlayer.currentTime >= playEndTime) {
                         console.log('Popup: Scene playback ended.');
                         popupPlayer.pause();
                         clearPopupEndCheck();
                         // Trigger next scene in queue if applicable
                         playNextSceneInQueue();
                     }
                 }, 100); // Check every 100ms
             }
         } else {
             // If metadata not loaded, wait for it
             $(popupPlayer).off('loadedmetadata.seekplay').one('loadedmetadata.seekplay', () => {
                 seekAndPlayInPopup(startTime, endTime, sceneData); // Retry after metadata loaded
             });
         }
     }

    function playSelectedScenesInPopup() {
        if (selectedScenes.size === 0) {
            alert('再生するシーンを選択してください。');
            return;
        }
        
        const selectedSceneObjects = scenes.filter(s => selectedScenes.has(s.id))
            .sort((a, b) => timecodeToSeconds(a.start_timecode) - timecodeToSeconds(b.start_timecode));
        
        if (selectedSceneObjects.length === 0) return;
        
        // Set up the global queue
        currentPlayQueue = selectedSceneObjects.map(s => ({
             start: timecodeToSeconds(s.start_timecode),
             end: timecodeToSeconds(s.end_timecode),
             sceneData: s // Pass full scene data
        }));
        currentPlayIndex = 0; // Reset global index
        
        // Start the first scene
        playNextSceneInQueue();
        console.log(`Starting playback queue in popup for ${currentPlayQueue.length} scenes`);
    }

    function playNextSceneInQueue() {
         if (!currentPlayQueue || currentPlayIndex >= currentPlayQueue.length) {
             console.log('Popup: Playback queue finished.');
             clearPopupEndCheck();
             currentPlayQueue = null; // Clear the queue
             // Optionally close popup or show message
             return;
         }
         const sceneToPlay = currentPlayQueue[currentPlayIndex];
         console.log(`Popup: Playing queue item ${currentPlayIndex + 1}/${currentPlayQueue.length}, Scene ID: ${sceneToPlay.sceneData.id}`);
         openPlayerAndPlay(sceneToPlay.start, sceneToPlay.end, sceneToPlay.sceneData);
         highlightTableRow(sceneToPlay.sceneData.id); // Highlight in main table
         currentPlayIndex++;
     }

    function handlePopupTimeUpdate() {
        if (popupPlayer.paused) return; // Don't update if paused
        const currentTime = popupPlayer.currentTime;
        // Highlight corresponding row in main window table
        highlightTableRowForTime(currentTime);
        // Update subtitle in popup
        updatePopupSubtitle(currentTime);
        // Update scene info in popup (if not in specific scene-play mode)
        if (playEndTime === null) { // Only update general scene info if not playing a specific scene segment
            updatePopupSceneInfo(findSceneDataByTime(currentTime));
        }
    }
    
    function handlePopupPause() {
        console.log("Popup player paused or ended.");
        // If playback was part of a queue and paused manually (not by interval), stop queue.
        if (playEndInterval) {
             console.log("Manual pause detected during scene playback. Stopping queue check.");
             clearPopupEndCheck();
             // Decide if queue should be cleared or just paused
             // currentPlayQueue = null; // Option: Clear queue on manual pause
        }
    }

    function handlePopupSeeked() {
        console.log("Popup player seeked.");
        clearPopupEndCheck(); // Clear end check on manual seek
        const currentTime = popupPlayer.currentTime;
        highlightTableRowForTime(currentTime);
        updatePopupSubtitle(currentTime);
        updatePopupSceneInfo(findSceneDataByTime(currentTime)); // Update info based on new time
    }

    function clearPopupEndCheck() {
        if (playEndInterval) {
            clearInterval(playEndInterval);
            playEndInterval = null;
            playEndTime = null; // Reset end time tracking
            console.log("Cleared scene end check interval.");
        }
    }

    function resetPlayer() {
        if (popupPlayer) {
            popupPlayer.pause();
            $(popupPlayer).find('source').removeAttr('src');
            popupPlayer.load(); // Reset the player state
        }
        clearPopupEndCheck();
        clearPopupSceneInfo();
        clearPopupSubtitle();
        console.log("Popup player reset.");
    }

    // --- Popup UI Update Functions ---
    function updatePopupSceneInfo(sceneData) {
         if (!sceneData) {
             // Optionally clear info or show 'No scene data'
             // clearPopupSceneInfo(); 
             return; 
         }
         // Avoid unnecessary updates if the scene hasn't changed
         if (currentScene && currentScene.id === sceneData.id) {
             return;
         }
         
         popupThumbnailImg.attr('src', sceneData.thumbnail_path ? `${API_BASE_URL}/thumbnails/${sceneData.id}` : 'placeholder.jpg');
         popupSceneIdSpan.text(sceneData.scene_id || '-');
         popupStartSpan.text(sceneData.start_timecode || '-');
         popupEndSpan.text(sceneData.end_timecode || '-');
         popupTagSpan.text(sceneData.scene_evaluation_tag || '-');
         popupDescriptionP.text(sceneData.description || '-');
         currentScene = sceneData; // Keep track of displayed scene
     }
     
     function clearPopupSceneInfo() {
         popupThumbnailImg.attr('src', 'placeholder.jpg');
         popupSceneIdSpan.text('-');
         popupStartSpan.text('-');
         popupEndSpan.text('-');
         popupTagSpan.text('-');
         popupDescriptionP.text('-');
         currentScene = null;
     }

     function updatePopupSubtitle(currentTime) {
         if (transcriptions.length === 0) {
             clearPopupSubtitle();
             return;
         }
         const currentTrans = transcriptions.find(t => {
             const start = timecodeToSeconds(t.start_timecode);
             const end = timecodeToSeconds(t.end_timecode);
             // Ensure start and end are valid numbers
             if (isNaN(start) || isNaN(end)) return false;
             return currentTime >= start && currentTime < end;
         });

         if (currentTrans && currentTrans.transcription) {
             // Avoid flickering by checking if text is different
             if (popupSubtitleDiv.text() !== currentTrans.transcription) {
                 popupSubtitleDiv.text(currentTrans.transcription).addClass('visible');
             }
         } else {
             // Clear only if it was previously visible
             if (popupSubtitleDiv.hasClass('visible')) {
                 clearPopupSubtitle();
             }
         }
     }

     function clearPopupSubtitle() {
         popupSubtitleDiv.text('').removeClass('visible');
     }
     
    // --- Main Table Highlight --- 
     function highlightTableRowForTime(currentTime) {
         const scene = findSceneDataByTime(currentTime);
         highlightTableRow(scene ? scene.id : null);
         // Optionally highlight transcription row
         // highlightTranscriptionRowForTime(currentTime);
     }

     function highlightTableRow(sceneId) {
        if (!scenesTable) return;
        // Use DataTables API for efficiency
        const rows = scenesTable.rows().nodes().to$(); // Get all row TR elements as jQuery object
        rows.removeClass('highlight-row'); // Clear all highlights first
        if (sceneId !== null) {
             // Find the specific row by data ID and add class
             scenesTable.rows(function(idx, data, node) {
                 return data.id === sceneId;
             }).nodes().to$().addClass('highlight-row');
             // Scrolling logic can be added here if needed
             // scenesTable.row(selector).scrollTo(false); // false = don't animate
        }
    }

    // --- Export Functions ---
    function exportEDL() {
        if (selectedScenes.size === 0) {
            alert('エクスポートするシーンを選択してください。');
            return;
        }
        const selectedSceneObjects = scenes.filter(s => selectedScenes.has(s.id));
        if (selectedSceneObjects.length === 0) return;
        selectedSceneObjects.sort((a, b) => timecodeToSeconds(a.start_timecode) - timecodeToSeconds(b.start_timecode));
        const exportData = { videoId: currentVideoId, scenes: selectedSceneObjects };

        fetch(`${API_BASE_URL}/export/edl`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(exportData),
        })
        .then(handleExportResponse)
        .catch(handleExportError('EDL'));
    }

    function exportSRT() {
        const selectedSceneIds = Array.from(selectedScenes);
        const selectedTranscriptions = transcriptions.filter(t => t.scene_id && selectedSceneIds.includes(t.scene_id));
        if (selectedTranscriptions.length === 0) {
            alert('エクスポート対象の字幕が見つかりません。');
            return;
        }
        selectedTranscriptions.sort((a, b) => timecodeToSeconds(a.start_timecode) - timecodeToSeconds(b.start_timecode));
        const exportData = { videoId: currentVideoId, transcriptions: selectedTranscriptions };

        fetch(`${API_BASE_URL}/export/srt`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(exportData),
        })
        .then(handleExportResponse)
        .catch(handleExportError('SRT'));
    }

    // --- Initialization Function ---
    // This function sets up the application after the DOM is ready
    async function initApp() {
        console.log("Initializing Excel-like UI application...");
        initTables(); // Initialize empty DataTables structure first
        await loadVideos(); // Load video list into selector
        initEventListeners(); // Set up event handlers
        updateButtonStates(); // Set initial button states (e.g., disable export)
        updateSelectedStats(); // Set initial selection stats
        updateSelectAllCheckboxState(); // Set initial state of select all checkbox
        console.log("Application initialized.");
    }

    // --- Execute Initialization ---
    // Call initApp only once, at the end, after all functions are defined.
    initApp();

}); // End of $(document).ready()
