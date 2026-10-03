const form = document.getElementById("subtitle-form");
const loadingSection = document.getElementById("loading-section");
const outputSection = document.getElementById("output-section");

const downloadBtn = outputSection.querySelector(".download-btn");
const watchBtn = outputSection.querySelector(".watch-btn");
const submitBtn = form.querySelector(
    "button[type='submit'], button:not([type]), input[type='submit']"
);

[downloadBtn, watchBtn].forEach(function (btn) {
    btn.removeAttribute("onclick");
});

let currentJobId = null;
let isProcessing = false;

const warningBox = document.createElement("p");
warningBox.style.cssText =
    "display:none; margin:12px 0; padding:10px 14px; border:1px solid #ff7300; " +
    "border-radius:10px; color:#ffb877; font-size:0.9rem;";
outputSection.insertBefore(warningBox, downloadBtn);

const anotherBtn = document.createElement("button");
anotherBtn.type = "button";
anotherBtn.className = watchBtn.className;
anotherBtn.textContent = "Generate Another";
outputSection.appendChild(anotherBtn);

function showForm() {
    loadingSection.style.display = "none";
    outputSection.style.display = "none";
    form.style.display = "block";
}

function setProcessing(on) {
    isProcessing = on;
    if (submitBtn) submitBtn.disabled = on;
}

async function readError(response) {
    try {
        const data = await response.json();
        if (data && data.error) return data.error;
    } catch (_) {

    }
    return "Server error (" + response.status + ")";
}

form.addEventListener("submit", async function (event) {
    event.preventDefault();
    if (isProcessing) return; 

    setProcessing(true);
    form.style.display = "none";
    loadingSection.style.display = "block";

    try {
        const response = await fetch("/upload", {
            method: "POST",
            body: new FormData(form)
        });

        if (!response.ok) {
            throw new Error(await readError(response));
        }

        const data = await response.json();
        if (!data || !data.job_id) {
            throw new Error("Unexpected response from the server.");
        }
        currentJobId = data.job_id;

        if (data.warnings && data.warnings.length > 0) {
            warningBox.textContent = data.warnings.join(" ");
            warningBox.style.display = "block";
        } else {
            warningBox.textContent = "";
            warningBox.style.display = "none";
        }

        loadingSection.style.display = "none";
        outputSection.style.display = "block";
    } catch (err) {
        const isNetworkError =
            err.name === "TypeError" && /fetch|network|load failed/i.test(err.message);
        const message = isNetworkError
            ? "Could not reach the server. Is it still running?"
            : err.message;
        loadingSection.style.display = "none";
        form.style.display = "block";
        alert("Something went wrong: " + message);
    } finally {
        setProcessing(false);
    }
});

downloadBtn.addEventListener("click", function () {
    if (!currentJobId) return;
    window.location.href = "/download/" + currentJobId;
});

watchBtn.addEventListener("click", function () {
    if (!currentJobId) return;
    window.open("/watch/" + currentJobId, "_blank");
});

anotherBtn.addEventListener("click", function () {
    currentJobId = null;
    warningBox.textContent = "";
    warningBox.style.display = "none";
    form.reset();
    showForm();
});