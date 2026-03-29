
document.addEventListener("DOMContentLoaded", () => {
    const coinButtons = document.querySelectorAll(".btn-coin");

    coinButtons.forEach(btn => {
        btn.addEventListener("click", () => {
            btn.classList.add("coin-clicked");
            setTimeout(() => btn.classList.remove("coin-clicked"), 200);
        });
    });
});
