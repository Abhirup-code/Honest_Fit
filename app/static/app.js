// While the local model thinks (it can take a little while), say so and stop double submits.
document.getElementById("analyze-form")?.addEventListener("submit", () => {
  const button = document.getElementById("analyze-button");
  const status = document.getElementById("analyze-status");
  if (button) {
    button.disabled = true;
    button.textContent = "Analyzing…";
  }
  if (status) status.textContent = "Analyzing. With local AI this can take up to a minute.";
});
