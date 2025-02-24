const socket = new WebSocket(`ws://${window.location.host}/ws`);
const chatMessages = $("#chat-messages");

socket.onmessage = function(event) {
    const data = JSON.parse(event.data);
    
    switch(data.type) {
        case "thinking":
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
        // Show thinking animation on submit
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

function renderResults(data) {
    let table = '';
    let summary = '';

    if (data.data && data.data.formatted_data && typeof data.data.formatted_data === 'object') {
        table = `
            <table class="table table-dark table-striped mt-3">
                <thead>
                    <tr>
                        <th>Metric</th>
                        <th>Value</th>
                    </tr>
                </thead>
                <tbody>
                    ${Object.entries(data.data.formatted_data).map(([key, value]) => `
                        <tr>
                            <td>${key.replace(/_/g, ' ')}</td>
                            <td>${value || 'N/A'}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
        summary = data.data.summary || '';
    } else if (data.output) {
        summary = data.output;
    } else {
        summary = 'No detailed data available.';
    }

    chatMessages.append(`
        <div class="message bot-message fade-in">
            ${table}
            <div class="summary mt-3">${summary}</div>
        </div>
    `);
}

$("#user-input").keypress(function(e) {
    if (e.which == 13) {
        sendMessage();
    }
});