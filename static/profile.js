document.getElementById("btnSupport").addEventListener("click", () => {
    document.getElementById("supportModal").classList.remove("hidden");
});

function closeSupport() {
    document.getElementById("supportModal").classList.add("hidden");
}

document.getElementById("supportForm").addEventListener("submit", async (e) => {
    e.preventDefault();

    const form = e.target;
    const formData = new FormData(form);

    try {
        const response = await fetch("/api/support", {
            method: "POST",
            body: formData
        });

        const data = await response.json();

        if (response.ok) {
            alert(data.message || "Support request sent!");
            form.reset();
            closeSupport();
        } else {
            alert(data.detail || "Error sending support request");
        }
    } catch (err) {
        console.error(err);
        alert("Failed to send support request");
    }
});
