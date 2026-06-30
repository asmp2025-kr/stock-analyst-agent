// Configuration
const APP_NAME = "app";
const USER_ID = "dashboard_user_" + Math.random().toString(36).substring(2, 9);
let sessionId = "";
let currentInterruptId = null;

// DOM Elements
const chatFeed = document.getElementById("chat-feed");
const chatInput = document.getElementById("chat-input");
const sendBtn = document.getElementById("send-btn");
const sessionDisplay = document.getElementById("session-display");
const newSessionBtn = document.getElementById("new-session-btn");
const hitlPanel = document.getElementById("hitl-panel");
const hitlMessage = document.getElementById("hitl-message");
const hitlApprove = document.getElementById("hitl-approve");
const hitlDeny = document.getElementById("hitl-deny");
const logConsole = document.getElementById("log-console");

// Metric Elements
const stockHeader = document.getElementById("stock-header");
const tickerDisplay = document.getElementById("ticker-display");
const stockSubtitle = document.getElementById("stock-subtitle");
const valPrice = document.getElementById("val-price");
const valChange = document.getElementById("val-change");
const valVolume = document.getElementById("val-volume");
const valCap = document.getElementById("val-cap");
const valPe = document.getElementById("val-pe");
const valDebt = document.getElementById("val-debt");
const valGrowth = document.getElementById("val-growth");
const valSentiment = document.getElementById("val-sentiment");

// Initialize application
async function init() {
    appendAuditLog("Initializing new session...", "system");
    await resetSession();
    
    // Set up listeners
    sendBtn.addEventListener("click", handleSendMessage);
    chatInput.addEventListener("keypress", (e) => {
        if (e.key === "Enter") handleSendMessage();
    });
    newSessionBtn.addEventListener("click", resetSession);
    
    hitlApprove.addEventListener("click", () => submitHitlResponse(true));
    hitlDeny.addEventListener("click", () => submitHitlResponse(false));
}

// Reset Session
async function resetSession() {
    try {
        const randId = Math.random().toString(36).substring(2, 15);
        const response = await fetch(`/apps/${APP_NAME}/users/${USER_ID}/sessions`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ session_id: randId })
        });
        
        const data = await response.json();
        sessionId = data.id;
        sessionDisplay.textContent = sessionId.substring(0, 8) + "...";
        
        // Clear chat UI
        chatFeed.innerHTML = `
            <div class="message assistant">
                <div class="avatar"><i class="fa-solid fa-robot"></i></div>
                <div class="message-content">
                    <h3>Stock Analyst Agent</h3>
                    <p>Session reset successfully. Awaiting stock query...</p>
                </div>
            </div>
        `;
        
        // Reset metrics
        stockHeader.classList.add("hidden");
        valPrice.textContent = "$--";
        valChange.textContent = "--";
        valChange.className = "badge";
        valVolume.textContent = "--";
        valCap.textContent = "--";
        valPe.textContent = "--";
        valDebt.textContent = "--";
        valGrowth.textContent = "--";
        valSentiment.textContent = "Select a stock to run market sentiment evaluation...";
        
        hitlPanel.classList.add("hidden");
        currentInterruptId = null;
        chatInput.disabled = false;
        
        appendAuditLog(`Session started: ${sessionId}`, "info");
    } catch (err) {
        appendAuditLog("Failed to create session: " + err.message, "critical");
    }
}

// Switch tabs
function switchTab(tabId) {
    document.querySelectorAll(".tab-btn").forEach(btn => btn.classList.remove("active"));
    document.querySelectorAll(".tab-content").forEach(content => content.classList.remove("active"));
    
    const activeBtn = event.target;
    activeBtn.classList.add("active");
    document.getElementById(`tab-${tabId}`).classList.add("active");
}

// Append log line to custom terminal console
function appendAuditLog(message, type = "info") {
    const time = new Date().toLocaleTimeString();
    const line = document.createElement("div");
    line.className = `log-line ${type}`;
    line.innerHTML = `[${time}] [${type.toUpperCase()}] ${escapeHtml(message)}`;
    logConsole.appendChild(line);
    logConsole.scrollTop = logConsole.scrollHeight;
}

// Escape HTML utility
function escapeHtml(text) {
    if (typeof text !== "string") return JSON.stringify(text);
    return text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

// Send Message
async function handleSendMessage() {
    const text = chatInput.value.trim();
    if (!text) return;
    
    chatInput.value = "";
    appendMessage(text, "user");
    await streamQuery({
        new_message: {
            role: "user",
            parts: [{ text: text }]
        }
    });
}

// Send a quick action from the sidebar
async function sendQuickQuery(queryText) {
    appendMessage(queryText, "user");
    await streamQuery({
        new_message: {
            role: "user",
            parts: [{ text: queryText }]
        }
    });
}

// Append chat speech bubble to feed
function appendMessage(text, sender) {
    const messageDiv = document.createElement("div");
    messageDiv.className = `message ${sender}`;
    
    const icon = sender === "user" ? "fa-user" : "fa-robot";
    const title = sender === "user" ? "You" : "Stock Analyst Agent";
    
    // Parse markdown headers, bold, and code formatting
    let formattedText = escapeHtml(text)
        .replace(/### (.*?)(?:\n|<br>|$)/g, "<h3>$1</h3>")
        .replace(/## (.*?)(?:\n|<br>|$)/g, "<h2>$1</h2>")
        .replace(/# (.*?)(?:\n|<br>|$)/g, "<h1>$1</h1>")
        .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
        .replace(/`(.*?)`/g, "<code>$1</code>")
        .replace(/\n/g, "<br>");

    messageDiv.innerHTML = `
        <div class="avatar"><i class="fa-solid ${icon}"></i></div>
        <div class="message-content">
            <h3>${title}</h3>
            <p>${formattedText}</p>
        </div>
    `;
    
    chatFeed.appendChild(messageDiv);
    chatFeed.scrollTop = chatFeed.scrollHeight;
    return messageDiv;
}

// Read SSE Stream and populate UI
async function streamQuery(payload) {
    // Disable inputs while running
    chatInput.disabled = true;
    sendBtn.disabled = true;
    
    const requestPayload = {
        app_name: APP_NAME,
        user_id: USER_ID,
        session_id: sessionId,
        streaming: true,
        ...payload
    };

    try {
        const response = await fetch("/run_sse", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(requestPayload)
        });

        if (!response.ok) {
            const errText = await response.text();
            throw new Error(errText || `Server responded with ${response.status}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        
        let assistantMessageDiv = null;
        let assistantMessageContent = "";
        let bufferedLine = "";

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;
            
            const chunk = decoder.decode(value, { stream: true });
            const lines = (bufferedLine + chunk).split("\n");
            bufferedLine = lines.pop(); // Keep incomplete line

            for (const line of lines) {
                if (line.startsWith("data: ")) {
                    const dataStr = line.slice(6).trim();
                    if (dataStr === "[DONE]") continue;
                    
                    try {
                        const parsed = JSON.parse(dataStr);
                        handleAgentEvent(parsed);

                        // Capture non-streamed python node outputs
                        if (parsed.output && typeof parsed.output === "string") {
                            const author = parsed.author || "";
                            if (author === "finalize_report" || author === "security_event" || author === "hitl_approval") {
                                appendMessage(parsed.output, "assistant");
                            }
                        }

                        // Capture actual assistant message text updates
                        if (parsed.content && parsed.content.parts) {
                            for (const part of parsed.content.parts) {
                                if (part.text) {
                                    if (!assistantMessageDiv) {
                                        assistantMessageDiv = appendMessage("", "assistant");
                                    }
                                    assistantMessageContent += part.text;
                                    
                                    // Live update bubble content
                                    const p = assistantMessageDiv.querySelector(".message-content p");
                                    let formatted = escapeHtml(assistantMessageContent)
                                        .replace(/### (.*?)(?:\n|<br>|$)/g, "<h3>$1</h3>")
                                        .replace(/## (.*?)(?:\n|<br>|$)/g, "<h2>$1</h2>")
                                        .replace(/# (.*?)(?:\n|<br>|$)/g, "<h1>$1</h1>")
                                        .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
                                        .replace(/`(.*?)`/g, "<code>$1</code>")
                                        .replace(/\n/g, "<br>");
                                    p.innerHTML = formatted;
                                    chatFeed.scrollTop = chatFeed.scrollHeight;
                                }
                            }
                        }
                    } catch (e) {
                        // Buffer error or parsed failure
                    }
                }
            }
        }
    } catch (err) {
        appendAuditLog(`Execution Error: ${err.message}`, "critical");
        appendMessage(`Error: ${err.message}. Please verify the backend logs or try resetting the session.`, "assistant");
    } finally {
        chatInput.disabled = false;
        sendBtn.disabled = false;
        chatInput.focus();
    }
}

// Process structural agent event types
function handleAgentEvent(event) {
    // 1. Audit logs from event output (e.g. security log)
    if (event.output) {
        const out = event.output;
        
        // Check if output is a security audit string or contains security info
        if (typeof out === "string") {
            if (out.includes("Security check failed") || out.includes("blocked")) {
                appendAuditLog(out, "critical");
            }
        }
        
        // Scan state for security events
        if (event.state) {
            const state = event.state;
            if (state.security_event) {
                appendAuditLog(`Blocked prompt injection or compliance breach: ${state.security_event}`, "critical");
            }
        }
    }
    
    // Check if the event comes from security node
    if (event.nodeName === "security_checkpoint") {
        appendAuditLog("Security check completed successfully.", "info");
    }

    // 2. Telemetry and method routing logs
    if (event.nodeName) {
        appendAuditLog(`Routing node execution: ${event.nodeName}`, "info");
    }

    // 3. Extract metrics data from the state dictionary if present
    if (event.state) {
        const state = event.state;
        updateStockMetricsPanel(state);
    }

    // 4. Human in the Loop (HITL) prompt interrupts
    if (event.interruptId) {
        currentInterruptId = event.interruptId;
        const msg = event.message || "Approval needed for transaction.";
        
        // Show HITL prompt panel
        hitlMessage.textContent = msg;
        hitlPanel.classList.remove("hidden");
        appendAuditLog("Interrupt triggered: Paused awaiting Human approval.", "warning");
    }
}

// Update side panel values based on the state delta of agents
function updateStockMetricsPanel(state) {
    // Attempt to extract information about ticker from the report or query state
    let queryText = state.query || "";
    let ticker = "";
    
    const tickerMatch = queryText.match(/\b(AAPL|GOOG|MSFT|TSLA)\b/i);
    if (tickerMatch) {
        ticker = tickerMatch[1].toUpperCase();
    } else {
        return; // No supported stock ticker found in query text
    }

    stockHeader.classList.remove("hidden");
    tickerDisplay.textContent = ticker;
    
    const companyNames = {
        AAPL: "Apple Inc. Corporate Analysis",
        GOOG: "Alphabet Inc. (Google) Analysis",
        MSFT: "Microsoft Corp. Performance",
        TSLA: "Tesla Inc. Financial Health"
    };
    stockSubtitle.textContent = companyNames[ticker] || `${ticker} Stock analysis`;

    // Populate mock technical and fundamental data matching app/mcp_server.py
    if (ticker === "AAPL") {
        setMetrics("$175.50", "+1.2%", "up", "85,000,000", "$2.75 Trillion", "28.5", "1.5", "+8.2%", "Overall strongly bullish. Driven by strong hardware services segment and positive sentiment on upcoming AI announcements.");
    } else if (ticker === "GOOG") {
        setMetrics("$172.80", "+2.5%", "up", "28,000,000", "$2.15 Trillion", "24.2", "0.4", "+14.2%", "Bullish sentiment. Supported by strong cloud growth, core search dominance, and positive analyst recommendations.");
    } else if (ticker === "MSFT") {
        setMetrics("$420.20", "-0.8%", "down", "22,000,000", "$3.12 Trillion", "35.8", "0.8", "+17.0%", "Neutral-bullish outlook. High P/E valuation is balanced by industry-leading cloud and copilot product integration.");
    } else if (ticker === "TSLA") {
        setMetrics("$180.10", "-4.2%", "down", "95,000,000", "$570 Billion", "45.1", "0.1", "-5.5%", "Bearish outlook. Significant headwind due to margin compression, vehicle delivery slowdown, and rising competitive pressure.");
    }
}

function setMetrics(price, change, direction, volume, cap, pe, debt, growth, sentiment) {
    valPrice.textContent = price;
    valChange.textContent = change;
    valChange.className = `badge ${direction}`;
    valVolume.textContent = volume;
    valCap.textContent = cap;
    valPe.textContent = pe;
    valDebt.textContent = debt;
    valGrowth.textContent = growth;
    valSentiment.textContent = sentiment;
}

// Respond to HITL confirmation buttons
async function submitHitlResponse(approved) {
    if (!currentInterruptId) return;
    
    // Hide panel
    hitlPanel.classList.add("hidden");
    appendAuditLog(`Submitting Human Response: approved=${approved}`, "info");
    
    // Submit response part via functionResponse payload
    const responsePayload = {
        new_message: {
            role: "user",
            parts: [{
                function_response: {
                    id: currentInterruptId,
                    response: { approved: approved }
                }
            }]
        }
    };
    
    currentInterruptId = null;
    await streamQuery(responsePayload);
}

// Start application
window.addEventListener("DOMContentLoaded", init);
