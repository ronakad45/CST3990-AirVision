/**
 * AirVision API Service — Public access (no auth needed)
 */

const API_BASE = '/api';

const api = {
    async get(endpoint) {
        try {
            const res = await axios.get(API_BASE + endpoint);
            return res.data;
        } catch (err) {
            console.error('GET ' + endpoint, err.response?.data || err.message);
            throw err;
        }
    },

    async post(endpoint, data) {
        try {
            const res = await axios.post(API_BASE + endpoint, data, {
                headers: { 'Content-Type': 'application/json' }
            });
            return res.data;
        } catch (err) {
            console.error('POST ' + endpoint, err.response?.data || err.message);
            throw err;
        }
    },

    // Air Quality
    getCurrentAQ(city) { return this.get('/current/' + encodeURIComponent(city)); },
    getHistorical(city, days) { return this.get('/historical/' + encodeURIComponent(city) + '?days=' + days); },
    compareCities(list) { return this.get('/compare?cities=' + list.join(',')); },
    getCities() { return this.get('/cities'); },

    // Weather
    getWeather(city) { return this.get('/weather/' + encodeURIComponent(city)); },

    // Forecast
    getForecast(city) { return this.get('/forecast/' + encodeURIComponent(city)); },
    getMultiForecast(city, days) { return this.get('/forecast/' + encodeURIComponent(city) + '/multi?days=' + days); },
    getModelComparison() { return this.get('/models/compare'); },

    // Quiz
    getQuizTopics() { return this.get('/quiz/topics'); },
    getQuizQuestions(topicId) { return this.get('/quiz/topics/' + topicId); },
    submitQuiz(playerName, topicId, answers, timeTaken) {
        return this.post('/quiz/submit', {
            player_name: playerName,
            topic_id: topicId,
            answers: answers,
            time_taken_sec: timeTaken
        });
    },

    // Leaderboard
    getLeaderboard() { return this.get('/quiz/leaderboard'); },
    getPlayerStats(name) { return this.get('/quiz/leaderboard/' + encodeURIComponent(name)); },
};
