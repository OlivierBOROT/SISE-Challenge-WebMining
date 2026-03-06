import { InputTracker } from './modules/inputTracker.js';
import { EventTracker } from './modules/interactionTracker.js';
import { drawTrackPlot } from './modules/mouseTrackPlot.js';
import { drawSpeedPlot } from './modules/mouseSpeedPlot.js';
import { drawScatterPlot } from './modules/scatterPlot.js';
import { initUserResult, setClusterResult } from './modules/userResult.js';
import { setBotResult } from './modules/botResult.js';

const inputTracker = new InputTracker();
const eventTracker = new EventTracker();




function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) {
        return parts.pop().split(';').shift();
    }
    return null;
}


let analysisInterval = 10; // secondes (doit correspondre à l'intervalle de trackInputs)
let timer = analysisInterval;
const timerElement = document.getElementById('analysis-timer');

function updateTimerDisplay() {
    if (timerElement) {
        timerElement.textContent = timer + 's';
    }
}

// Timer visuel qui décrémente chaque seconde
setInterval(() => {
    timer--;
    if (timer < 0) timer = analysisInterval;
    updateTimerDisplay();
}, 1000);


function trackInputs() {
    inputTracker.start();
    setInterval(async () => {
        const stats = inputTracker.computeFeatures();
        inputTracker.reset();
        
        document.dispatchEvent(new CustomEvent('inputTrackerReset', {
            bubbles: true,
            cancelable: false
        }))

        if (stats === null || stats === undefined) {
            return;
        }

        // Attach optional source label injected externally (e.g. by Selenium bots)
        if (window.__TRACKER_SOURCE__) {
            stats._source = window.__TRACKER_SOURCE__;
        }

        // Send stats to python
        try {
            const response = await fetch('ajax/track_inputs', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    stats: stats,
                    session_id: getCookie('session_id')
                })
            })
            timer = analysisInterval;
            updateTimerDisplay();
            if (response.ok) {
                const result = await response.json();
                if (result.label !== undefined) {
                    setBotResult(result.label, result.score ?? 0, result.confidence ?? 0, result.persona ?? "unknown");
                }
            }
        } catch (err) {
            console.warn('[trackInputs] fetch failed:', err);
            timer = analysisInterval;
            updateTimerDisplay();
        }
    }, analysisInterval * 1000);
}


function trackEvents() {
    eventTracker.start();
    setInterval(async () => {
        const payload = eventTracker.flush();

        if (!payload.events.length) {
            return;
        }

        // Attach optional source label injected externally (e.g. by Selenium bots)
        if (window.__TRACKER_SOURCE__) {
            payload._source = window.__TRACKER_SOURCE__;
        }

        try {
            const response = await fetch('ajax/track_events', {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json' 
                },
                body: JSON.stringify({
                    events: payload,
                    session_id: getCookie('session_id')
                }),
            });
            if (response.ok) {
                const result = await response.json();
                if (!result.warning) {
                    setClusterResult(result.label.toString());
                    document.dispatchEvent(new CustomEvent('behaviourUpdate', {
                        detail: result,
                        bubbles: true,
                        cancelable: false
                    }))
                }
            }
        } catch (err) {
            console.warn('[trackEvents] fetch failed:', err);
        }
    }, 1000);
}


async function renderClusters() {
    const response = await fetch('ajax/projection');
    const content = await response.json();
    drawScatterPlot(content.plot);
    // Reset highlighted cluster display initially
    try {
        if (typeof window.highlightCluster === 'function') window.highlightCluster(null);
    } catch (e) {
        console.warn('highlightCluster not available', e);
    }
    // Display total number of clusters in the stat box
    try {
        const scEl = document.getElementById('sc-highlighted');
        if (scEl) {
            const total = content.clusters ? Object.keys(content.clusters).length : (window.CLUSTERS ? window.CLUSTERS.length : '—');
            scEl.textContent = total;
        }
    } catch (e) {
        console.warn('Unable to set total clusters', e);
    }
    // Show PCA explained variance and axis labels under the scatter plot
    if (content.pca) {
        try {
            const compPerc = content.pca.explained_by_component || [0,0];
            window.setScatterVarianceInfo(
                content.pca.explained_variance || 0,
                content.pca.x_label || 'Composante 1',
                content.pca.y_label || 'Composante 2',
                compPerc
            );
        } catch (e) {
            // function may not be defined in older clients
            console.warn('setScatterVarianceInfo not available', e);
        }
    }
}


// Render analytics plots
drawTrackPlot();
drawSpeedPlot();
initUserResult();
renderClusters();

// Track user inputs (mouse, clicks, scroll, form)
trackInputs();

// Track user events (product, category, page interactions)
trackEvents();
