const MATERIALS_ENDPOINT = "/api/materials";
const DOWNLOAD_ENDPOINT = "/api/materials/download";

const category = document.body?.dataset?.materialCategory || "";
const materialsGrid = document.getElementById("materials-grid");
const materialsStatus = document.getElementById("materials-status");

function setStatus(text) {
    if (materialsStatus) {
        materialsStatus.textContent = text;
    }
}

function createCard(item) {
    const card = document.createElement(item.available ? "a" : "article");
    card.className = `material-card ${item.available ? "is-available" : "is-unavailable"}`;

    if (item.available) {
        card.href = `${DOWNLOAD_ENDPOINT}?file=${encodeURIComponent(item.file_name)}`;
        card.setAttribute("aria-label", `Baixar ${item.title}`);
    }

    const title = document.createElement("h3");
    title.className = "material-title";
    title.textContent = item.title;

    const type = document.createElement("p");
    type.className = "material-type";
    type.textContent = "PDF";

    const action = document.createElement("p");
    action.className = "material-action";
    action.textContent = item.status;

    card.appendChild(title);
    card.appendChild(type);
    card.appendChild(action);

    return card;
}

function renderErrorCard(message) {
    if (!materialsGrid) {
        return;
    }

    const card = document.createElement("article");
    card.className = "material-card is-unavailable";

    const title = document.createElement("h3");
    title.className = "material-title";
    title.textContent = "Nao foi possivel carregar";

    const detail = document.createElement("p");
    detail.className = "material-type";
    detail.textContent = message;

    const action = document.createElement("p");
    action.className = "material-action";
    action.textContent = "Tente novamente em instantes";

    card.appendChild(title);
    card.appendChild(detail);
    card.appendChild(action);

    materialsGrid.innerHTML = "";
    materialsGrid.appendChild(card);
}

async function loadMaterials() {
    if (!category || !materialsGrid) {
        return;
    }

    setStatus("Carregando materiais...");

    try {
        const response = await fetch(`${MATERIALS_ENDPOINT}?category=${encodeURIComponent(category)}`);
        const payload = await response.json();

        if (!response.ok) {
            throw new Error(payload.error || "Erro ao consultar materiais.");
        }

        const items = Array.isArray(payload.items) ? payload.items : [];

        materialsGrid.innerHTML = "";
        items.forEach((item) => {
            materialsGrid.appendChild(createCard(item));
        });

        const availableCount = items.filter((item) => item.available).length;
        const upcomingCount = items.length - availableCount;

        if (!items.length) {
            setStatus("Nenhum material encontrado");
            return;
        }

        if (upcomingCount > 0) {
            setStatus(`${availableCount} disponiveis | ${upcomingCount} em breve`);
            return;
        }

        setStatus(`${availableCount} materiais disponiveis`);
    } catch (error) {
        const message = error instanceof Error ? error.message : "Falha inesperada.";
        setStatus("Falha ao carregar materiais");
        renderErrorCard(message);
    }
}

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
    const nodeCount = isMobile ? 46 : 80;
    const maxDistance = isMobile ? 120 : 150;

    function resizeCanvas() {
        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;
    }

    function createNodes() {
        nodes.length = 0;
        for (let i = 0; i < nodeCount; i += 1) {
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

                if (dist < maxDistance) {
                    const alpha = (1 - dist / maxDistance) * 0.15;
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

loadMaterials();
initNeuralCanvas("neural-bg");
