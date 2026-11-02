document.addEventListener("DOMContentLoaded", () => {
  const input = document.querySelector("#id_file");
  const label = document.querySelector(".upload-title");
  if (!input || !label) return;

  input.addEventListener("change", () => {
    if (!input.files || !input.files.length) return;
    const fileName = input.files[0].name;
    label.textContent = fileName.length > 42 ? `${fileName.slice(0, 39)}…` : fileName;
  });
});
