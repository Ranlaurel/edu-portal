(function () {
  const root = document.getElementById("exam-root");
  const questions = window.EXAM_QUESTIONS || [];
  const examId = window.EXAM_ID;
  const draftKey = "oge-exam-draft-" + examId;
  let state = loadDraft();

  function loadDraft() {
    try {
      return JSON.parse(localStorage.getItem(draftKey) || "{}") || {};
    } catch (e) {
      return {};
    }
  }

  function saveDraft() {
    try {
      localStorage.setItem(draftKey, JSON.stringify(state));
    } catch (e) {
      /* private mode / storage blocked: answers just aren't kept across reloads */
    }
  }

  function el(tag, cls, text) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    return e;
  }

  function set(qid, value) {
    state[qid] = value;
    saveDraft();
  }

  function renderQuestion(q) {
    const card = el("div", "question-card exam-card");
    const head = el("div", "exam-task-head");
    head.appendChild(el("span", "exam-task-num", "Задание " + q.task));
    head.appendChild(el("span", "q-type-label", q.task_title + " · " + pointsLabel(q.points)));
    card.appendChild(head);
    OgeMedia.renderContext(card, q);

    if (q.type === "self_check") {
      const text = el("div", "question-text rich");
      text.innerHTML = q.html; // our own content, rendered from markdown on the server
      card.appendChild(text);
      if (q.listen_text) OgeMedia.renderListen(card, q.listen_text);
      if (q.no_text) {
        card.appendChild(el("div", "quiz-hint", "Здесь ничего писать не нужно: оценишь свои тексты на шаге самопроверки."));
        return card;
      }
      const area = el("textarea", "exam-textarea");
      area.rows = 12;
      area.placeholder = "Напиши ответ здесь. После завершения варианта сверишь его с эталоном и критериями ФИПИ.";
      area.value = (state[q.id] && state[q.id].text) || "";
      area.addEventListener("input", () => set(q.id, { text: area.value }));
      card.appendChild(area);
      return card;
    }

    card.appendChild(el("div", "question-text", q.text));

    if (q.type === "single" || q.type === "multiple") {
      const list = el("div", "option-list");
      q.options.forEach((opt) => {
        const item = el("div", "option", opt.text);
        const chosen = q.type === "single" ? state[q.id] === opt.id : (state[q.id] || []).includes(opt.id);
        if (chosen) item.classList.add("selected");
        item.addEventListener("click", () => {
          if (q.type === "single") {
            [...list.children].forEach((c) => c.classList.remove("selected"));
            item.classList.add("selected");
            set(q.id, opt.id);
          } else {
            const cur = new Set(state[q.id] || []);
            cur.has(opt.id) ? cur.delete(opt.id) : cur.add(opt.id);
            item.classList.toggle("selected");
            set(q.id, [...cur]);
          }
        });
        list.appendChild(item);
      });
      card.appendChild(list);
    } else if (q.type === "dropdown") {
      card.appendChild(selectFor(q.options, state[q.id], (v) => set(q.id, v)));
    } else if (q.type === "fill_blank") {
      const input = el("input", "q-fill");
      input.type = "text";
      input.placeholder = "Ответ";
      input.value = state[q.id] || "";
      input.addEventListener("input", () => set(q.id, input.value));
      card.appendChild(input);
    } else if (q.type === "matching") {
      // Exam form: a dropdown per left item instead of the drag-lines UI.
      const current = Object.assign({}, state[q.id] || {});
      q.left.forEach((left) => {
        const row = el("div", "exam-match-row");
        row.appendChild(el("span", "", left.text));
        row.appendChild(
          selectFor(q.right, current[left.id], (v) => {
            current[left.id] = v;
            set(q.id, Object.assign({}, current));
          })
        );
        card.appendChild(row);
      });
    }
    return card;
  }

  function selectFor(options, selected, onChange) {
    const select = el("select", "q-select");
    select.appendChild(el("option", "", "— выбери —"));
    options.forEach((opt) => {
      const o = el("option", "", opt.text);
      o.value = opt.id;
      if (selected === opt.id) o.selected = true;
      select.appendChild(o);
    });
    select.addEventListener("change", () => onChange(parseInt(select.value, 10) || null));
    return select;
  }

  function pointsLabel(n) {
    const mod10 = n % 10;
    const mod100 = n % 100;
    if (mod10 === 1 && mod100 !== 11) return n + " балл";
    if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return n + " балла";
    return n + " баллов";
  }

  questions.forEach((q) => root.appendChild(renderQuestion(q)));

  // Timer is a guide, like the clock on the wall in the exam room: when it runs out
  // we show it, but don't throw away work by auto-submitting.
  const timer = document.getElementById("exam-timer");
  const deadline = new Date(timer.dataset.started).getTime() + Number(timer.dataset.minutes) * 60000;
  function tick() {
    const left = Math.round((deadline - Date.now()) / 1000);
    if (left <= 0) {
      timer.textContent = "Время вышло — заверши вариант";
      timer.classList.add("exam-timer-over");
      return;
    }
    const h = Math.floor(left / 3600);
    const m = Math.floor((left % 3600) / 60);
    const s = left % 60;
    timer.textContent = "Осталось " + h + ":" + String(m).padStart(2, "0") + ":" + String(s).padStart(2, "0");
    timer.classList.toggle("exam-timer-low", left < 15 * 60);
  }
  tick();
  setInterval(tick, 1000);

  const submitBtn = document.getElementById("exam-submit");
  submitBtn.addEventListener("click", async () => {
    const unanswered = questions.filter((q) => {
      const v = state[q.id];
      if (q.type === "self_check" && q.no_text) return false;
      return v === undefined || v === null || v === "" || (q.type === "self_check" && !q.no_text && !(v.text || "").trim());
    }).length;
    if (unanswered && !confirm("Без ответа заданий: " + unanswered + ". Всё равно завершить?")) return;
    submitBtn.disabled = true;
    const res = await fetch(`/oge/exam/${examId}/submit`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ answers: state }),
    });
    if (!res.ok) {
      submitBtn.disabled = false;
      alert("Не получилось отправить ответы. Проверь соединение и попробуй ещё раз — ответы сохранены.");
      return;
    }
    const data = await res.json();
    try {
      localStorage.removeItem(draftKey);
    } catch (e) {}
    window.location.href = data.redirect;
  });
})();
