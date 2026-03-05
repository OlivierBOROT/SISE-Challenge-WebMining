import { InputTracker } from './modules/inputTracker.js';
import { EventTracker } from './modules/interactionTracker.js';
import { drawTrackPlot } from './modules/mouseTrackPlot.js';
import { drawSpeedPlot } from './modules/mouseSpeedPlot.js';
import { initUserResult, setClusterResult } from './modules/userResult.js';

const inputTracker = new InputTracker();
const eventTracker = new EventTracker({ userId: inputTracker.sessionId });




function trackInputs() {
    inputTracker.start();
    setInterval(async () => {
        const stats = inputTracker.computeFeatures();
        inputTracker.reset();
        
        document.dispatchEvent(new CustomEvent('inputTrackerReset', {
            bubbles: true,
            cancelable: false
        }))

        if (!stats) {
            return
        }

        console.log('POST ajax/track_inputs', stats);
        // Attach optional source label injected externally (e.g. by Selenium bots)
        const payload = { ...stats, _source: window.__TRACKER_SOURCE__ || 'human' };
        // Send stats to python
        const response = await fetch('ajax/track_inputs', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(payload)
        })
        const content = await response.json();
        // TODO: display result: {is_bot: bool, bot_score: float}
    }, 15000);
}




function trackEvents() {
    eventTracker.start();
    setInterval(async () => {
        const payload = eventTracker.flush();

        if (!payload.events.length) {
            return;
        }

        console.log('POST ajax/track_events', payload);

        const response = await fetch('ajax/track_events', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
        const result = await response.json();
        // Response handling (kept minimal)
        console.log('RESPONSE ajax/track_events', { ok: response.ok, status: response.status });
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
