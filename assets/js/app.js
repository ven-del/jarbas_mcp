const API_ENDPOINT = "/api/chat";

const chatForm = document.getElementById("chat-form");
const chatInput = document.getElementById("chat-input");
const chatMessages = document.getElementById("chat-messages");
const chatStatus = document.getElementById("chat-status");
const sendBtn = document.getElementById("send-btn");
const clearChatBtn = document.getElementById("clear-chat");

const history = [];

function setStatus(text) {
    chatStatus.textContent = text;
}

function pushHistory(role, content) {
    history.push({ role, content });
    if (history.length > 24) {
        history.splice(0, history.length - 24);
    }
}

function addMessage(role, text, temporary = false) {
    const messageEl = document.createElement("article");
    messageEl.className = `message ${role}`;
    if (temporary) {
        messageEl.dataset.temporary = "true";
    }

    const textEl = document.createElement("p");
    textEl.textContent = text;

    messageEl.appendChild(textEl);
    chatMessages.appendChild(messageEl);
    chatMessages.scrollTop = chatMessages.scrollHeight;

    return messageEl;
}

function resetConversation() {
    history.length = 0;
    chatMessages.innerHTML = "";
    addMessage(
        "assistant",
        "Nova conversa iniciada. Manda sua pergunta sobre IA Generativa e bora destrinchar!"
    );
    setStatus("Pronto para responder");
}

async function sendMessage(userMessage) {
    setStatus("Buscando contexto no RAG...");
    sendBtn.disabled = true;
    chatInput.disabled = true;

    const loadingBubble = addMessage("assistant", "Jarbas esta pensando...", true);

    try {
        const response = await fetch(API_ENDPOINT, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                message: userMessage,
                history,
            }),
        });

        const data = await response.json();
        loadingBubble.remove();

        if (!response.ok) {
            addMessage("assistant", data.error || "Falhei em responder agora.");
            setStatus("Falha na requisicao");
            return;
        }

        const answer = (data.answer || "").trim() || "Nao consegui responder agora.";
        addMessage("assistant", answer);
        pushHistory("assistant", answer);

        if (data.context_found) {
            setStatus("Contexto encontrado na base");
        } else {
            setStatus("Sem contexto relevante na base");
        }
    } catch (_error) {
        loadingBubble.remove();
        addMessage("assistant", "Conexao falhou. Tente novamente em instantes.");
        setStatus("Erro de conexao");
    } finally {
        sendBtn.disabled = false;
        chatInput.disabled = false;
        chatInput.focus();
    }
}

chatForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const userMessage = chatInput.value.trim();
    if (!userMessage) {
        return;
    }

    addMessage("user", userMessage);
    pushHistory("user", userMessage);

    chatInput.value = "";
    await sendMessage(userMessage);
});

chatInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        chatForm.requestSubmit();
    }
});

clearChatBtn.addEventListener("click", () => {
    resetConversation();
    chatInput.focus();
});

function initNeuralCanvas(canvasId) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) {
        return;
    }

    const ctx = canvas.getContext("2d");
    if (!ctx) {
        return;
    }

    const nodes = [];
    const isMobile = window.matchMedia("(max-width: 768px)").matches;
    const NODE_COUNT = isMobile ? 46 : 80;
    const MAX_DISTANCE = isMobile ? 120 : 150;

    function resizeCanvas() {
        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;
    }

    function createNodes() {
        nodes.length = 0;
        for (let i = 0; i < NODE_COUNT; i += 1) {
            nodes.push({
                x: Math.random() * canvas.width,
                y: Math.random() * canvas.height,
                vx: (Math.random() - 0.5) * 0.4,
                vy: (Math.random() - 0.5) * 0.4,
                radius: Math.random() * 2 + 1,
            });
        }
    }

    function draw() {
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        for (let i = 0; i < nodes.length; i += 1) {
            for (let j = i + 1; j < nodes.length; j += 1) {
                const dx = nodes[i].x - nodes[j].x;
                const dy = nodes[i].y - nodes[j].y;
                const dist = Math.sqrt(dx * dx + dy * dy);

                if (dist < MAX_DISTANCE) {
                    const alpha = (1 - dist / MAX_DISTANCE) * 0.15;
                    ctx.strokeStyle = `rgba(0, 229, 200, ${alpha})`;
                    ctx.lineWidth = 0.8;
                    ctx.beginPath();
                    ctx.moveTo(nodes[i].x, nodes[i].y);
                    ctx.lineTo(nodes[j].x, nodes[j].y);
                    ctx.stroke();
                }
            }
        }

        nodes.forEach((node) => {
            const glow = ctx.createRadialGradient(node.x, node.y, 0, node.x, node.y, node.radius * 4);
            glow.addColorStop(0, "rgba(0, 229, 200, 0.3)");
            glow.addColorStop(1, "rgba(0, 229, 200, 0)");

            ctx.fillStyle = glow;
            ctx.beginPath();
            ctx.arc(node.x, node.y, node.radius * 4, 0, Math.PI * 2);
            ctx.fill();

            ctx.fillStyle = "rgba(0, 229, 200, 0.6)";
            ctx.beginPath();
            ctx.arc(node.x, node.y, node.radius, 0, Math.PI * 2);
            ctx.fill();

            node.x += node.vx;
            node.y += node.vy;

            if (node.x < 0 || node.x > canvas.width) {
                node.vx *= -1;
            }
            if (node.y < 0 || node.y > canvas.height) {
                node.vy *= -1;
            }
        });

        requestAnimationFrame(draw);
    }

    resizeCanvas();
    createNodes();
    draw();

    window.addEventListener("resize", () => {
        resizeCanvas();
        createNodes();
    });
}

initNeuralCanvas("neural-bg");
