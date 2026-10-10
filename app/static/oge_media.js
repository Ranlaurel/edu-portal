// Shared bits for ОГЭ questions, used by quiz.js and oge_exam.js.
window.OgeMedia = (function () {
  let lastContext = null;

  // Shared text/table/SVG above a question. Consecutive questions built on the same
  // context (math tasks 1-5) show it once, the rest get a short back-reference.
  function renderContext(card, q) {
    if (!q.context_html) return;
    if (q.context_html === lastContext) {
      card.appendChild(Object.assign(document.createElement("div"), {
        className: "context-ref",
        textContent: "Условие — в тексте выше.",
      }));
      return;
    }
    lastContext = q.context_html;
    const box = document.createElement("div");
    box.className = "question-context rich";
    box.innerHTML = q.context_html; // our own content, rendered from markdown on the server
    card.appendChild(box);
  }

  // Изложение: on the exam the text is heard twice and never shown. Uses the browser's
  // Russian voice; without one, falls back to showing the text to read (twice) and hide.
  function renderListen(card, text) {
    const wrap = document.createElement("div");
    wrap.className = "listen-box";
    let left = 2;
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "btn btn-secondary";
    const hint = document.createElement("div");
    hint.className = "quiz-hint";
    hint.textContent = "Как на экзамене: текст звучит дважды. Во время прослушивания делай записи в черновике.";

    const synth = window.speechSynthesis;
    const ruVoice = () => (synth ? synth.getVoices().find((v) => v.lang && v.lang.toLowerCase().startsWith("ru")) : null);
    const label = () => (btn.textContent = left > 0 ? "▶ Прослушать текст (осталось: " + left + ")" : "Прослушивания закончились");
    label();

    btn.addEventListener("click", async () => {
      if (left <= 0) return;
      if (synth && !synth.getVoices().length) {
        // Voices load asynchronously in some browsers -- give them a moment.
        await new Promise((resolve) => {
          synth.addEventListener("voiceschanged", resolve, { once: true });
          setTimeout(resolve, 1500);
        });
      }
      const voice = ruVoice();
      if (!voice) {
        showText();
        return;
      }
      left -= 1;
      label();
      btn.disabled = true;
      synth.cancel();
      const u = new SpeechSynthesisUtterance(text);
      u.voice = voice;
      u.lang = "ru-RU";
      u.rate = 0.9;
      u.onend = u.onerror = () => {
        btn.disabled = left <= 0;
      };
      synth.speak(u);
    });

    function showText() {
      btn.style.display = "none";
      hint.textContent = "В браузере нет русского голоса. Попроси кого-нибудь прочитать текст вслух дважды или прочитай сам два раза — потом скрой его и пиши.";
      const body = document.createElement("div");
      body.className = "rich listen-text";
      body.textContent = text;
      const hide = document.createElement("button");
      hide.type = "button";
      hide.className = "btn btn-secondary";
      hide.textContent = "Скрыть текст";
      hide.addEventListener("click", () => {
        body.remove();
        hide.remove();
        hint.textContent = "Текст скрыт. Пиши изложение по памяти и записям.";
      });
      wrap.appendChild(body);
      wrap.appendChild(hide);
    }

    wrap.appendChild(btn);
    wrap.appendChild(hint);
    card.appendChild(wrap);
  }

  return { renderContext, renderListen };
})();
