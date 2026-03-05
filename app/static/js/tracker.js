import { InputTracker } from './modules/inputTracker.js';
import { EventTracker } from './modules/interactionTracker.js';
import { drawTrackPlot } from './modules/mouseTrackPlot.js';
import { drawSpeedPlot } from './modules/mouseSpeedPlot.js';
import { initUserResult, setClusterResult } from './modules/userResult.js';

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
        const result = await response.json();
    }, 10000);
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
        const result = await response.json();
    }, 1000);
}


// Render analytics plots
drawTrackPlot();
drawSpeedPlot();
initUserResult();

// Track user inputs (mouse, clicks, scroll, form)
trackInputs();

// Track user events (product, category, page interactions)
trackEvents();
