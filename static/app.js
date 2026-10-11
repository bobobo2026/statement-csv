(() => {
  const dropzone = document.getElementById("dropzone");
  const fileInput = document.getElementById("file-input");
  const fileMeta = document.getElementById("file-meta");
  const fileName = document.getElementById("file-name");
  const btnParse = document.getElementById("btn-parse");
  const errorEl = document.getElementById("error");
  const statusEl = document.getElementById("status");
  const result = document.getElementById("result");
  const balanceBox = document.getElementById("balance-box");
  const txCount = document.getElementById("tx-count");
  const tbody = document.querySelector("#tx-table tbody");
  const btnCsv = document.getElementById("btn-csv");
  const btnXlsx = document.getElementById("btn-xlsx");

  let selectedFile = null;
  let lastTransactions = [];

  function track(event) {
    try {
      fetch("/api/event", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ event }),
        keepalive: true,
      }).catch(() => {});
    } catch (_) {}
  }

  function showError(msg) {
    errorEl.hidden = !msg;
    errorEl.textContent = msg || "";
  }
  function showStatus(msg) {
    statusEl.hidden = !msg;
    statusEl.textContent = msg || "";
  }
  function money(v) {
    if (v === null || v === undefined || v === "") return "";
    return Number(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }

  function setFile(file) {
    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      showError("Please choose a PDF file.");
      return;
    }
    selectedFile = file;
    fileName.textContent = `${file.name} (${(file.size / 1024).toFixed(1)} KB)`;
    fileMeta.hidden = false;
    showError("");
    result.hidden = true;
    track("file_selected");
  }

  dropzone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropzone.classList.add("drag");
  });
  dropzone.addEventListener("dragleave", () => dropzone.classList.remove("drag"));
  dropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropzone.classList.remove("drag");
    const f = e.dataTransfer.files?.[0];
    setFile(f);
  });
  fileInput.addEventListener("change", () => setFile(fileInput.files?.[0]));

  function renderBalance(bc) {
    if (!bc) {
      balanceBox.className = "balance unknown";
      balanceBox.innerHTML = `<div class="title">Balance check unavailable</div>`;
      return;
    }
    const cls = bc.passed === true ? "pass" : bc.passed === false ? "fail" : "unknown";
    const title =
      bc.passed === true ? "✓ Balance check passed" :
      bc.passed === false ? "✗ Balance check failed" :
      "? Balance check incomplete";
    balanceBox.className = `balance ${cls}`;
    balanceBox.innerHTML = `
      <div class="title">${title}</div>
      <p>${bc.message || ""}</p>
      <div class="grid">
        <div>Opening<strong>${money(bc.opening)}</strong></div>
        <div>Deposits<strong>${money(bc.total_deposits)}</strong></div>
        <div>Withdrawals<strong>${money(bc.total_withdrawals)}</strong></div>
        <div>Computed<strong>${money(bc.computed_closing)}</strong></div>
        <div>Closing<strong>${money(bc.closing)}</strong></div>
        <div>Difference<strong>${money(bc.difference)}</strong></div>
      </div>`;
  }

  function renderTable(txs) {
    tbody.innerHTML = "";
    txs.forEach((t) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${t.date || ""}</td>
        <td>${escapeHtml(t.description || "")}</td>
        <td class="num">${money(t.deposit)}</td>
        <td class="num">${money(t.withdrawal)}</td>
        <td class="num">${money(t.balance)}</td>`;
      tbody.appendChild(tr);
    });
    txCount.textContent = `(${txs.length})`;
  }

  function escapeHtml(s) {
    return s.replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    }[c]));
  }

  async function download(path, filename) {
    const res = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ transactions: lastTransactions }),
    });
    if (!res.ok) throw new Error("Download failed");
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  }

  btnParse.addEventListener("click", async () => {
    if (!selectedFile) return;
    showError("");
    showStatus("Parsing in memory…");
    btnParse.disabled = true;
    try {
      const fd = new FormData();
      fd.append("file", selectedFile);
      const res = await fetch("/api/parse", { method: "POST", body: fd });
      const data = await res.json();
      if (data.error === "no_text_layer") {
        showError(data.message);
        showStatus("");
        result.hidden = true;
        return;
      }
      if (!data.ok && !data.transactions) {
        showError(data.message || "Parse failed");
        showStatus("");
        return;
      }
      lastTransactions = data.transactions || [];
      renderBalance(data.balance_check);
      renderTable(lastTransactions);
      result.hidden = false;
      showStatus(data.message || "Done. File was not retained.");
    } catch (e) {
      showError(String(e.message || e));
      showStatus("");
    } finally {
      btnParse.disabled = false;
    }
  });

  btnCsv.addEventListener("click", () => download("/api/download/csv", "transactions.csv").catch((e) => showError(e.message)));
  btnXlsx.addEventListener("click", () => download("/api/download/xlsx", "transactions.xlsx").catch((e) => showError(e.message)));
})();
