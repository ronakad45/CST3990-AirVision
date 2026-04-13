/**
 * AirVision — Vue.js App (No login required)
 * Public dashboard with weather, forecasts, quiz with leaderboard.
 */

new Vue({
    el: '#app',

    data: {
        // Navigation
        currentView: 'dashboard',
        selectedCity: 'Dubai',
        cities: ['Dubai', 'Abu Dhabi', 'Riyadh', 'Kuwait City', 'Doha'],

        // Dashboard
        currentAQ: {},
        pollutantCards: [],
        modelMetrics: [],
        todayForecast: null,
        weather: null,
        dashboardChart: null,
        forecastBarChart: null,

        // Forecast
        forecast: null,
        multiForecast: [],
        forecastChart: null,

        // Compare
        compareCities: ['Dubai', 'Riyadh', 'Kuwait City'],
        compareResults: [],

        // Trends
        trendDays: 30,
        trendStats: null,
        trendsChart: null,

        // Quiz
        quizState: 'hub',
        quizTopics: [],
        quizQuestions: [],
        quizAnswers: {},
        currentQuestionIdx: 0,
        currentTopicId: null,
        quizStartTime: null,
        quizResult: null,
        playerName: localStorage.getItem('playerName') || '',
        showNamePrompt: false,
        pendingTopicId: null,

        // Leaderboard
        leaderboard: [],
        playerStats: null,

        // Mobile
        showMobileMenu: false,

        // Loading
        loading: false,
    },

    computed: {
        pageTitle() {
            return {
                dashboard: 'Dashboard',
                forecast: 'Forecast',
                compare: 'Compare Cities',
                trends: 'Historical Trends',
                quiz: 'Quiz & Learn',
                leaderboard: 'Leaderboard',
            }[this.currentView] || 'AirVision';
        },

        currentQuestion() {
            return this.quizQuestions[this.currentQuestionIdx] || null;
        },

        weatherIcon() {
            if (!this.weather) return '';
            return this.weather.icon_url || '';
        },
    },

    watch: {
        currentView(v) {
            if (v === 'dashboard') this.loadDashboard();
            if (v === 'forecast') this.loadForecast();
            if (v === 'compare') this.compareResults = [];
            if (v === 'trends') this.loadTrends();
            if (v === 'quiz') { this.quizState = 'hub'; this.loadQuizTopics(); }
            if (v === 'leaderboard') this.loadLeaderboard();
        },
        selectedCity() {
            if (this.currentView === 'dashboard') this.loadDashboard();
            if (this.currentView === 'forecast') this.loadForecast();
            if (this.currentView === 'trends') this.loadTrends();
        }
    },

    mounted() {
        this.loadDashboard();
    },

    methods: {
        // ═══ DASHBOARD ═══
        async loadDashboard() {
            await Promise.all([
                this.loadCurrentAQ(),
                this.loadTodayForecast(),
                this.loadWeather(),
                this.loadModelMetrics(),
            ]);
            await this.loadDashboardChart();
            await this.loadCityComparisonBar();
        },

        async loadCurrentAQ() {
            try {
                const data = await api.getCurrentAQ(this.selectedCity);
                this.currentAQ = data;
                this.pollutantCards = [
                    { label: 'PM2.5', value: data.pm25, unit: 'µg/m³', level: this.lvl(data.pm25, 35) },
                    { label: 'PM10', value: data.pm10, unit: 'µg/m³', level: this.lvl(data.pm10, 150) },
                    { label: 'NO₂', value: data.no2, unit: 'µg/m³', level: this.lvl(data.no2, 100) },
                    { label: 'O₃', value: data.o3, unit: 'µg/m³', level: this.lvl(data.o3, 70) },
                    { label: 'CO', value: data.co, unit: 'ppm', level: this.lvl(data.co, 9) },
                    { label: 'SO₂', value: data.so2, unit: 'µg/m³', level: this.lvl(data.so2, 75) },
                ];
            } catch (e) {
                this.currentAQ = { aqi: '—', category: 'No data', color: '#6B7280', health_advisory: 'No data available.' };
                this.pollutantCards = [];
            }
        },

        async loadTodayForecast() {
            try { this.todayForecast = await api.getForecast(this.selectedCity); }
            catch (e) { this.todayForecast = null; }
        },

        async loadWeather() {
            try { this.weather = await api.getWeather(this.selectedCity); }
            catch (e) { this.weather = null; }
        },

        lvl(v, t) {
            if (v == null) return '';
            return v <= t * 0.5 ? 'good' : v <= t ? 'moderate' : 'unhealthy';
        },

        async loadDashboardChart() {
            try {
                const data = await api.getHistorical(this.selectedCity, 365);
                const r = data.readings || [];
                if (this.dashboardChart) this.dashboardChart.destroy();

                // Determine which pollutant to show (PM2.5 if available, else PM10)
                const hasPM25 = r.some(x => x.pm25 != null);
                const hasPM10 = r.some(x => x.pm10 != null);
                const primaryPollutant = hasPM25 ? 'pm25' : (hasPM10 ? 'pm10' : null);
                const primaryLabel = hasPM25 ? 'PM2.5 (µg/m³)' : 'PM10 (µg/m³)';

                if (!primaryPollutant || r.length === 0) return;

                // Build datasets
                const datasets = [{
                    label: primaryLabel, data: r.map(x => x[primaryPollutant]),
                    borderColor: '#3B82F6', backgroundColor: 'rgba(59,130,246,0.1)',
                    fill: true, tension: 0.4, pointRadius: r.length > 100 ? 0 : 2,
                }, {
                    label: 'AQI', data: r.map(x => x.aqi),
                    borderColor: '#F59E0B', fill: false, tension: 0.4, pointRadius: r.length > 100 ? 0 : 2,
                    yAxisID: 'y1',
                }];

                // Add secondary pollutant if available
                if (hasPM25 && hasPM10) {
                    datasets.push({
                        label: 'PM10', data: r.map(x => x.pm10),
                        borderColor: '#8B5CF6', fill: false, tension: 0.4, pointRadius: 0,
                        borderDash: [5, 5],
                    });
                }

                this.$nextTick(() => {
                    const ctx = document.getElementById('dashboardChart');
                    if (!ctx) return;
                    this.dashboardChart = new Chart(ctx, {
                        type: 'line',
                        data: {
                            labels: r.map(x => x.timestamp ? x.timestamp.substring(5, 10) : ''),
                            datasets: datasets
                        },
                        options: {
                            responsive: true,
                            interaction: { intersect: false, mode: 'index' },
                            scales: {
                                y: { title: { display: true, text: primaryLabel }, beginAtZero: true },
                                y1: { position: 'right', title: { display: true, text: 'AQI' }, beginAtZero: true, grid: { drawOnChartArea: false } },
                            },
                            plugins: { legend: { position: 'top' } }
                        }
                    });
                });
            } catch (e) { console.error(e); }
        },

        async loadCityComparisonBar() {
            try {
                const allCities = ['Dubai', 'Abu Dhabi', 'Riyadh', 'Kuwait City', 'Doha'];
                const aqis = [];
                const colors = [];
                const labels = [];

                for (const city of allCities) {
                    try {
                        const d = await api.getCurrentAQ(city);
                        labels.push(city);
                        aqis.push(d.aqi || 0);
                        colors.push(d.color || '#6B7280');
                    } catch (e) { /* skip cities without data */ }
                }

                if (this.forecastBarChart) this.forecastBarChart.destroy();
                this.$nextTick(() => {
                    const ctx = document.getElementById('cityBarChart');
                    if (!ctx) return;
                    this.forecastBarChart = new Chart(ctx, {
                        type: 'bar',
                        data: {
                            labels: labels,
                            datasets: [{
                                label: 'Current AQI',
                                data: aqis,
                                backgroundColor: colors.map(c => c + '99'),
                                borderColor: colors,
                                borderWidth: 2,
                                borderRadius: 6,
                            }]
                        },
                        options: {
                            responsive: true,
                            scales: { y: { beginAtZero: true, title: { display: true, text: 'AQI' } } },
                            plugins: { legend: { display: false } }
                        }
                    });
                });
            } catch (e) { console.error(e); }
        },

        async loadModelMetrics() {
            try {
                const data = await api.getModelComparison();
                const models = data.models || [];
                let best = Infinity;
                models.forEach(m => { if (m.rmse < best) best = m.rmse; });
                this.modelMetrics = models.map(m => ({ ...m, is_best: m.rmse === best }));
            } catch (e) { console.error(e); }
        },

        onCityChange() {
            if (this.currentView === 'dashboard') this.loadDashboard();
        },

        // ═══ FORECAST ═══
        async loadForecast() {
            this.loading = true;
            try { this.forecast = await api.getForecast(this.selectedCity); this.forecast.city = this.selectedCity; }
            catch (e) { this.forecast = null; }
            try {
                const d = await api.getMultiForecast(this.selectedCity, 5);
                this.multiForecast = d.forecasts || [];
            } catch (e) { this.multiForecast = []; }
            this.loading = false;

            // Draw forecast chart
            this.$nextTick(() => {
                if (this.forecastChart) this.forecastChart.destroy();
                const ctx = document.getElementById('forecastLineChart');
                if (!ctx || !this.multiForecast.length) return;
                this.forecastChart = new Chart(ctx, {
                    type: 'line',
                    data: {
                        labels: this.multiForecast.map(f => f.forecast_date.substring(5)),
                        datasets: [{
                            label: 'Predicted AQI',
                            data: this.multiForecast.map(f => f.predicted_aqi),
                            borderColor: '#EF4444',
                            backgroundColor: 'rgba(239,68,68,0.1)',
                            fill: true, tension: 0.3, pointRadius: 5, pointBackgroundColor: '#EF4444',
                        }, {
                            label: 'Predicted PM2.5',
                            data: this.multiForecast.map(f => f.predicted_pm25),
                            borderColor: '#3B82F6',
                            fill: false, tension: 0.3, pointRadius: 5,
                            yAxisID: 'y1',
                        }]
                    },
                    options: {
                        responsive: true,
                        scales: {
                            y: { title: { display: true, text: 'AQI' }, beginAtZero: true },
                            y1: { position: 'right', title: { display: true, text: 'PM2.5 (µg/m³)' }, beginAtZero: true, grid: { drawOnChartArea: false } },
                        },
                        plugins: { legend: { position: 'top' } }
                    }
                });
            });
        },

        // ═══ COMPARE ═══
        async compareCitiesData() {
            try {
                const d = await api.compareCities(this.compareCities);
                this.compareResults = (d.cities || []).map(c => ({
                    ...c, color: c.color || '#6B7280', category: c.category || 'Unknown',
                }));
            } catch (e) { console.error(e); }
        },

        // ═══ TRENDS ═══
        async loadTrends() {
            try {
                // Use at least 365 days to ensure we get data
                const fetchDays = Math.max(this.trendDays, 365);
                const data = await api.getHistorical(this.selectedCity, fetchDays);
                const allReadings = data.readings || [];

                // Filter to requested range if we fetched more
                const cutoff = new Date();
                cutoff.setDate(cutoff.getDate() - this.trendDays);
                const r = this.trendDays < 365 ? allReadings.filter(x => new Date(x.timestamp) >= cutoff) : allReadings;

                this.trendStats = { average_aqi: data.average_aqi, peak_aqi: data.peak_aqi, min_aqi: data.min_aqi, total_readings: r.length };

                // Determine which pollutant to chart
                const hasPM25 = r.some(x => x.pm25 != null);
                const hasPM10 = r.some(x => x.pm10 != null);
                const pollutant = hasPM25 ? 'pm25' : (hasPM10 ? 'pm10' : null);
                const pollLabel = hasPM25 ? 'PM2.5 (µg/m³)' : 'PM10 (µg/m³)';

                if (this.trendsChart) this.trendsChart.destroy();
                if (!pollutant || r.length === 0) return;

                const datasets = [{
                    label: pollLabel, data: r.map(x => x[pollutant]),
                    borderColor: '#3B82F6', backgroundColor: 'rgba(59,130,246,0.08)',
                    fill: true, tension: 0.3, pointRadius: r.length > 60 ? 0 : 3,
                }];

                // Add NO2 or O3 as secondary line if available
                const hasNO2 = r.some(x => x.no2 != null);
                const hasO3 = r.some(x => x.o3 != null);
                if (hasNO2) {
                    datasets.push({
                        label: 'NO₂ (µg/m³)', data: r.map(x => x.no2),
                        borderColor: '#EF4444', fill: false, tension: 0.3, pointRadius: 0, borderDash: [4,4],
                    });
                }
                if (hasO3) {
                    datasets.push({
                        label: 'O₃ (µg/m³)', data: r.map(x => x.o3),
                        borderColor: '#22C55E', fill: false, tension: 0.3, pointRadius: 0, borderDash: [4,4],
                    });
                }

                this.$nextTick(() => {
                    const ctx = document.getElementById('trendsChart');
                    if (!ctx) return;
                    this.trendsChart = new Chart(ctx, {
                        type: 'line',
                        data: {
                            labels: r.map(x => x.timestamp ? x.timestamp.substring(0, 10) : ''),
                            datasets: datasets
                        },
                        options: {
                            responsive: true,
                            interaction: { intersect: false, mode: 'index' },
                            scales: { y: { title: { display: true, text: pollLabel }, beginAtZero: true }, x: { ticks: { maxTicksLimit: 15 } } },
                            plugins: { legend: { position: 'top' } }
                        }
                    });
                });
            } catch (e) { console.error(e); }
        },

        // ═══ QUIZ ═══
        async loadQuizTopics() {
            try { this.quizTopics = (await api.getQuizTopics()).topics || []; }
            catch (e) { console.error(e); }
        },

        requestStartQuiz(topicId) {
            if (this.playerName.trim()) {
                this.startQuiz(topicId);
            } else {
                this.pendingTopicId = topicId;
                this.showNamePrompt = true;
            }
        },

        confirmName() {
            if (!this.playerName.trim()) { alert('Please enter your name'); return; }
            localStorage.setItem('playerName', this.playerName.trim());
            this.showNamePrompt = false;
            if (this.pendingTopicId) this.startQuiz(this.pendingTopicId);
        },

        async startQuiz(topicId) {
            try {
                const d = await api.getQuizQuestions(topicId);
                this.quizQuestions = d.questions || [];
                this.currentTopicId = topicId;
                this.quizAnswers = {};
                this.currentQuestionIdx = 0;
                this.quizStartTime = Date.now();
                this.quizState = 'active';
            } catch (e) { alert('Failed to load quiz.'); }
        },

        selectAnswer(qid, opt) { this.$set(this.quizAnswers, String(qid), opt); },
        nextQ() { if (this.currentQuestionIdx < this.quizQuestions.length - 1) this.currentQuestionIdx++; },
        prevQ() { if (this.currentQuestionIdx > 0) this.currentQuestionIdx--; },

        async submitQuiz() {
            const unanswered = this.quizQuestions.filter(q => !this.quizAnswers[String(q.question_id)]);
            if (unanswered.length) { alert(unanswered.length + ' questions unanswered!'); return; }
            const time = Math.round((Date.now() - this.quizStartTime) / 1000);
            try {
                this.quizResult = await api.submitQuiz(this.playerName || 'Anonymous', this.currentTopicId, this.quizAnswers, time);
                this.quizState = 'results';
            } catch (e) { alert('Submit failed.'); }
        },

        // ═══ LEADERBOARD ═══
        async loadLeaderboard() {
            try { this.leaderboard = (await api.getLeaderboard()).leaderboard || []; }
            catch (e) { console.error(e); }
        },
    }
});