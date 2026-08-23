const form = document.getElementById("subtitle-form");
 
const loadingSection =
document.getElementById("loading-section");
 
const outputSection =
document.getElementById("output-section");
 
const downloadBtn = document.querySelector(".download-btn");
const watchBtn = document.querySelector(".watch-btn");
 
form.addEventListener("submit", async function(event) {
    event.preventDefault();
 
    form.style.display = "none";
    loadingSection.style.display = "block";
 
    const formData = new FormData(form);
 
    try {
        const response = await fetch("/upload", {
            method: "POST",
            body: formData
        });
 
        // FIX 1 & 3: check if Flask returned an error
        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(errorText || "Server error: " + response.status);
        }
 
        // FIX 2: response is now actually used to confirm success
        const text = await response.text();
 
        if (!text || text.includes("Error") || text.includes("failed")) {
            throw new Error("Subtitle generation failed. Please try again.");
        }
 
        loadingSection.style.display = "none";
        outputSection.style.display = "block";
 
    } catch (err) {
        loadingSection.style.display = "none";
        alert("Something went wrong: " + err.message);
        form.style.display = "block";
    }
 
});
 
// FIX 4: button logic handled here in JS instead of inline onclick in HTML
downloadBtn.addEventListener("click", function() {
    window.location.href = "/download";
});
 
watchBtn.addEventListener("click", function() {
    window.open("/watch");
});