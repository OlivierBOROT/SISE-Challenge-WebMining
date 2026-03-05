import { InputTracker } from './modules/inputTracker.js';
import { drawTrackPlot } from './modules/mouseTrackPlot.js';
import { drawSpeedPlot } from './modules/mouseSpeedPlot.js';
import { initUserResult, setClusterResult } from './modules/userResult.js';

const inputTracker = new InputTracker()




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

        if (!stats) {
            return
        }

        console.log(stats);
        // Attach optional source label injected externally (e.g. by Selenium bots)
        const payload = { ...stats, _source: window.__TRACKER_SOURCE__ || 'human' };
        // Send stats to python
        const response = await fetch('ajax/track_inputs', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                stats: payload,
                session_id: getCookie('session_id')
            })
        })
        const content = await response.json();
        // TODO: display result: {is_bot: bool, bot_score: float}
    }, 1000);
}



// Render analytics plots
drawTrackPlot();
drawSpeedPlot();
initUserResult();

// Track user inputs
trackInputs();