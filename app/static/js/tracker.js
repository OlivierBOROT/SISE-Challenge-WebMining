import { InputTracker } from './modules/input_tracker.js';

const inputTracker = new InputTracker()




function trackInputs() {
    inputTracker.start();
    setInterval(async () => {
        const stats = inputTracker.computeFeatures();
        inputTracker.reset();
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
            body: JSON.stringify(payload)
        })
        const content = await response.json();
        // TODO: display result: {is_bot: bool, bot_score: float}
    }, 15000);
}


trackInputs();