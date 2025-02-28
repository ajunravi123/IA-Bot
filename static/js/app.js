const socket = new WebSocket(`ws://${window.location.host}/ws`);
const chatMessages = $("#chat-messages");

socket.onmessage = function(event) {
    const data = JSON.parse(event.data);
    
    switch(data.type) {
        case "thinking":
            $(".thinking-animation").remove();
            chatMessages.append(`
                <div class="thinking-animation">
                    <div class="thinking-spinner"></div>
                    <div class="thinking-dot"></div>
                    <div class="thinking-dot"></div>
                    <div class="thinking-dot"></div>
                </div>
            `);
            break;
        case "question":
            chatMessages.append(`<div class="message bot-message fade-in">${data.message}</div>`);
            break;
        case "message":
            $(".thinking-animation").remove();
            chatMessages.append(`<div class="message bot-message fade-in">${data.content}</div>`);
            break;
        case "result":
            $(".thinking-animation").remove();
            renderResults(data);
            break;
        case "error":
            $(".thinking-animation").remove();
            chatMessages.append(`<div class="message bot-message text-danger fade-in">Error: ${data.message}</div>`);
            break;
    }
    chatMessages.scrollTop(chatMessages[0].scrollHeight);
};

function sendMessage() {
    const input = $("#user-input");
    const message = input.val().trim();
    if (message) {
        chatMessages.append(`<div class="message user-message fade-in">${message}</div>`);
        socket.send(message);
        chatMessages.append(`
            <div class="thinking-animation">
                <div class="thinking-spinner"></div>
                <div class="thinking-dot"></div>
                <div class="thinking-dot"></div>
                <div class="thinking-dot"></div>
            </div>
        `);
        chatMessages.scrollTop(chatMessages[0].scrollHeight);
        input.val("");
    }
}

function parseBenefitValue(value) {
    if (value === "Not Available") return 0;
    const match = value.match(/(\d+\.?\d*)\s*([BKM]?)$/i);
    if (!match) return parseFloat(value.replace(/[^0-9.]/g, '')) || 0;
    const num = parseFloat(match[1]);
    const suffix = match[2].toUpperCase();
    return num * (suffix === 'B' ? 1e9 : suffix === 'M' ? 1e6 : suffix === 'K' ? 1e3 : 1);
}

// Store Chart instances to manage them
const chartInstances = new Map();

function createBarChart(canvasId, labels, lowValues, highValues, currency) {
    const canvas = document.getElementById(canvasId);
    const ctx = canvas.getContext('2d');

    // Destroy any existing chart instance for this canvas
    if (chartInstances.has(canvasId)) {
        chartInstances.get(canvasId).destroy();
    }

    // Create new chart and store it
    const newChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Low Estimate',
                data: lowValues,
                backgroundColor: 'rgba(54, 162, 235, 0.5)',
                borderColor: 'rgba(54, 162, 235, 1)',
                borderWidth: 1
            }, {
                label: 'High Estimate',
                data: highValues,
                backgroundColor: 'rgba(75, 192, 192, 0.5)',
                borderColor: 'rgba(75, 192, 192, 1)',
                borderWidth: 1
            }]
        },
        options: {
            scales: {
                y: {
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: `Value (${currency})`
                    }
                },
                x: {
                    title: {
                        display: true,
                        text: 'Benefits'
                    }
                }
            },
            plugins: {
                legend: {
                    display: true,
                    position: 'top'
                }
            }
        }
    });

    chartInstances.set(canvasId, newChart);
}

function renderResults(data) {
    let financialTable = '';
    let benefitsTable = '';
    let barChart = '';
    let summary = '';

    // Financial Data Table
    if (data.data && data.data.financial_data && typeof data.data.financial_data === 'object') {
        const currency = data.data.financial_data.currency || '';
        financialTable = `
            <h4>Financial Data</h4>
            <table class="table table-dark table-striped mt-3">
                <thead>
                    <tr>
                        <th>Field</th>
                        <th>Value</th>
                    </tr>
                </thead>
                <tbody>
                    ${Object.entries(data.data.financial_data).map(([key, value]) => {
                        const monetaryFields = ["balance_sheet_inventory_cost", "P&L_inventory_cost", "Revenue", "Salary Average", "gross_profit", "market_cap"];
                        let displayValue = value || 'N/A';
                        if (monetaryFields.includes(key) && value && value !== "Not Available") {
                            displayValue = `${value}`;
                        }
                        return `
                            <tr>
                                <td>${key.replace(/_/g, ' ')}</td>
                                <td>${displayValue}</td>
                            </tr>
                        `;
                    }).join('')}
                </tbody>
            </table>
        `;
    }

    // Benefits Table and Bar Chart
    if (data.data && data.data.benefits && typeof data.data.benefits === 'object') {
        const currency = data.data.financial_data.currency || '';
        benefitsTable = `
            <h4>Calculated Benefits</h4>
            <table class="table table-dark table-striped mt-3">
                <thead>
                    <tr>
                        <th>Benefit</th>
                        <th>Low Estimate</th>
                        <th>High Estimate</th>
                    </tr>
                </thead>
                <tbody>
                    ${Object.entries(data.data.benefits).map(([key, value]) => `
                        <tr>
                            <td>${key.replace(/_/g, ' ')}</td>
                            <td>${value.low || 'N/A'}</td>
                            <td>${value.high || 'N/A'}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;

        // Prepare data for bar chart
        const labels = Object.keys(data.data.benefits);
        const lowValues = labels.map(key => parseBenefitValue(data.data.benefits[key].low));
        const highValues = labels.map(key => parseBenefitValue(data.data.benefits[key].high));

        // Create unique canvas ID
        const canvasId = `benefitsChart_${Date.now()}`;
        barChart = `
            <h4>Benefits Bar Graph</h4>
            <canvas id="${canvasId}" width="400" height="200" class="mt-3"></canvas>
        `;

        // Append content first, then create the chart
        chatMessages.append(`
            <div class="message bot-message fade-in">
                ${financialTable}
                ${benefitsTable}
                ${barChart}
                <div class="summary mt-3">${data.data.summary || 'Financial benefits calculated.'}</div>
            </div>
        `);

        // Initialize the chart after appending
        createBarChart(canvasId, labels, lowValues, highValues, currency);
    } else {
        chatMessages.append(`
            <div class="message bot-message fade-in">
                ${financialTable}
                <div class="summary mt-3">No benefits calculated due to insufficient data.</div>
            </div>
        `);
    }

    chatMessages.scrollTop(chatMessages[0].scrollHeight);
}

$("#user-input").keypress(function(e) {
    if (e.which == 13) {
        sendMessage();
    }
});