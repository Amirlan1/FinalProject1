async function consentGetMe(){
  const r = await fetch("/api/me", { credentials: "same-origin" });
  if (!r.ok) return null;
  return await r.json();
}

function consentShow(){
  const ov = document.getElementById("consentOverlay");
  if (!ov) return;

  const chk = document.getElementById("consentChk");
  const btn = document.getElementById("consentBtn");
  const err = document.getElementById("consentErr");

  ov.style.display = "flex";
  chk.checked = false;
  btn.disabled = true;

  chk.onchange = () => { btn.disabled = !chk.checked; };

  btn.onclick = async () => {
    err.style.display = "none";
    btn.disabled = true;

    const r = await fetch("/api/consent/accept", {
      method: "POST",
      credentials: "same-origin"
    });

    if (r.ok){
      ov.style.display = "none";
      return;
    }

    btn.disabled = false;
    err.textContent = "Failed to accept. Try again.";
    err.style.display = "block";
  };
}

async function consentInit(){
  const me = await consentGetMe();
  if (!me) return;                 // не залогинен → ничего
  if (!me.privacyAccepted) consentShow();
}

document.addEventListener("DOMContentLoaded", consentInit);