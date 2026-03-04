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
        // Send stats to python
        const response = await fetch('ajax/track_inputs', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(stats)
        })
        const content = await response.json();
        // TODO: display result: {is_bot: bool, bot_score: float}
    }, 15000);
}


trackInputs();