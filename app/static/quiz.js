(function () {
  const root = document.getElementById("quiz-root");
  const questions = window.QUIZ_QUESTIONS || [];
  const topicId = window.QUIZ_TOPIC_ID;
  const state = {}; // questionId -> answer value
  const matchState = {}; // questionId -> { leftId: rightId }
  let submitted = false;

  function el(tag, cls, text) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    return e;
  }

  function renderQuestion(q, index) {
    const card = el("div", "question-card");
    card.id = "q-card-" + q.id;
    const label = el("div", "q-type-label", typeLabel(q.type));
    const text = el("div", "question-text", (index + 1) + ". " + q.text);
    card.appendChild(label);
    card.appendChild(text);

    if (q.type === "single" || q.type === "multiple") {
      const list = el("div", "option-list");
      q.options.forEach((opt) => {
        const item = el("div", "option");
        item.dataset.optionId = opt.id;
        item.textContent = opt.text;
        item.addEventListener("click", () => {
          if (submitted) return;
          if (q.type === "single") {
            state[q.id] = opt.id;
            [...list.children].forEach((c) => c.classList.remove("selected"));
            item.classList.add("selected");
          } else {
            const cur = new Set(state[q.id] || []);
            if (cur.has(opt.id)) {
              cur.delete(opt.id);
              item.classList.remove("selected");
            } else {
              cur.add(opt.id);
              item.classList.add("selected");
            }
            state[q.id] = [...cur];
          }
        });
        list.appendChild(item);
      });
      card.appendChild(list);
    } else if (q.type === "dropdown") {
      const select = el("select", "q-select");
      select.appendChild(el("option", "", "— выбери вариант —"));
      q.options.forEach((opt) => {
        const o = el("option", "", opt.text);
        o.value = opt.id;
        select.appendChild(o);
      });
      select.addEventListener("change", () => {
        state[q.id] = parseInt(select.value, 10) || null;
      });
      card.appendChild(select);
    } else if (q.type === "fill_blank") {
      const input = el("input", "q-fill");
      input.type = "text";
      input.placeholder = "Впиши ответ...";
      input.addEventListener("input", () => {
        state[q.id] = input.value;
      });
      card.appendChild(input);
    } else if (q.type === "matching") {
      renderMatching(card, q);
    }

    const explanation = el("div", "explanation", "");
    card.appendChild(explanation);
    return card;
  }

  function typeLabel(type) {
    return {
      single: "Один правильный ответ",
      multiple: "Несколько правильных ответов",
      dropdown: "Выбери из списка",
      fill_blank: "Впиши ответ",
      matching: "Соедини пары",
    }[type] || "";
  }

  function renderMatching(card, q) {
    const wrap = el("div", "match-wrap");
    const cols = el("div", "match-cols");
    const leftCol = el("div", "match-col");
    const rightCol = el("div", "match-col");

    matchState[q.id] = {};
    let selectedLeft = null;

    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("class", "match-svg");

    function redrawLines() {
      svg.innerHTML = "";
      const wrapRect = wrap.getBoundingClientRect();
      Object.entries(matchState[q.id]).forEach(([leftId, rightId]) => {
        const leftEl = leftCol.querySelector(`[data-pair-id="${leftId}"]`);
        const rightEl = rightCol.querySelector(`[data-pair-id="${rightId}"]`);
        if (!leftEl || !rightEl) return;
        const lr = leftEl.getBoundingClientRect();
        const rr = rightEl.getBoundingClientRect();
        const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
        line.setAttribute("x1", lr.right - wrapRect.left);
        line.setAttribute("y1", lr.top + lr.height / 2 - wrapRect.top);
        line.setAttribute("x2", rr.left - wrapRect.left);
        line.setAttribute("y2", rr.top + rr.height / 2 - wrapRect.top);
        line.dataset.leftId = leftId;
        svg.appendChild(line);
      });
    }

    q.left.forEach((p) => {
      const item = el("div", "match-item", p.text);
      item.dataset.pairId = p.id;
      item.addEventListener("click", () => {
        if (submitted) return;
        leftCol.querySelectorAll(".match-item").forEach((i) => i.classList.remove("selected"));
        selectedLeft = p.id;
        item.classList.add("selected");
      });
      leftCol.appendChild(item);
    });

    q.right.forEach((p) => {
      const item = el("div", "match-item", p.text);
      item.dataset.pairId = p.id;
      item.addEventListener("click", () => {
        if (submitted || selectedLeft === null) return;
        // free up right if already used by another left
        for (const [lid, rid] of Object.entries(matchState[q.id])) {
          if (rid === p.id) delete matchState[q.id][lid];
        }
        matchState[q.id][selectedLeft] = p.id;
        state[q.id] = matchState[q.id];
        leftCol.querySelectorAll(".match-item").forEach((i) => {
          i.classList.toggle("paired", matchState[q.id].hasOwnProperty(i.dataset.pairId));
          i.classList.remove("selected");
        });
        selectedLeft = null;
        redrawLines();
      });
      rightCol.appendChild(item);
    });

    cols.appendChild(leftCol);
    cols.appendChild(rightCol);
    wrap.appendChild(svg);
    wrap.appendChild(cols);
    card.appendChild(wrap);

    window.addEventListener("resize", redrawLines);
    setTimeout(redrawLines, 50);
    card._redrawLines = redrawLines;
  }

  questions.forEach((q, i) => root.appendChild(renderQuestion(q, i)));

  document.getElementById("submit-btn").addEventListener("click", async () => {
    const res = await fetch(`/topics/${topicId}/quiz/submit`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ answers: state }),
    });
    const data = await res.json();
    applyResults(data);
  });

  function applyResults(data) {
    submitted = true;
    document.getElementById("submit-btn").style.display = "none";
    document.getElementById("retry-link").style.display = "inline-block";

    const summary = document.getElementById("quiz-summary");
    summary.style.display = "block";
    summary.className = "quiz-summary " + (data.passed ? "pass" : "fail");
    summary.textContent = data.passed
      ? `Отлично! ${data.correct_count}/${data.total} верно (${data.score}%). Тема пройдена.`
      : `${data.correct_count}/${data.total} верно (${data.score}%). Нужно 70% — попробуй ещё раз.`;

    data.results.forEach((r) => {
      const card = document.getElementById("q-card-" + r.id);
      card.classList.add("answered");
      card.classList.add(r.correct ? "result-correct" : "result-incorrect");
      const explanation = card.querySelector(".explanation");
      if (explanation) explanation.textContent = r.explanation || "";

      const q = questions.find((qq) => qq.id === r.id);
      if (q.type === "single" || q.type === "multiple" || q.type === "dropdown") {
        markOptions(card, q, r);
      } else if (q.type === "fill_blank") {
        const input = card.querySelector("input.q-fill");
        input.disabled = true;
        input.classList.add(r.correct ? "correct" : "incorrect");
        if (!r.correct) {
          const hint = el("div", "explanation", "Правильный ответ: " + r.correct_answer);
          hint.style.display = "block";
          card.insertBefore(hint, card.querySelector(".explanation"));
        }
      } else if (q.type === "matching") {
        markMatching(card, q, r);
      }
    });

    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function markOptions(card, q, r) {
    const correctSet = new Set(r.correct_options || []);
    if (q.type === "dropdown") {
      const select = card.querySelector("select.q-select");
      select.disabled = true;
      const chosen = state[q.id];
      select.classList.add(correctSet.has(chosen) ? "correct" : "incorrect");
      return;
    }
    const chosen = new Set(q.type === "single" ? [state[q.id]] : state[q.id] || []);
    card.querySelectorAll(".option").forEach((item) => {
      const id = parseInt(item.dataset.optionId, 10);
      const isCorrect = correctSet.has(id);
      const wasChosen = chosen.has(id);
      if (wasChosen && isCorrect) item.classList.add("correct");
      else if (wasChosen && !isCorrect) item.classList.add("incorrect");
      else if (!wasChosen && isCorrect) item.classList.add("correct-missed");
    });
  }

  function markMatching(card, q, r) {
    const mapping = matchState[q.id] || {};
    card.querySelectorAll(".match-item").forEach((item) => {
      const pid = item.dataset.pairId;
      const isLeft = item.parentElement === item.closest(".match-cols").children[0];
      let correct;
      if (isLeft) correct = mapping[pid] === Number(pid) || String(mapping[pid]) === String(pid);
      else {
        // right item is correct if some left maps to it correctly
        correct = Object.entries(mapping).some(([lid, rid]) => String(rid) === String(pid) && String(lid) === String(pid));
      }
      item.classList.add(correct ? "correct" : "incorrect");
    });
    if (card._redrawLines) card._redrawLines();
    // colorize lines
    const svg = card.querySelector(".match-svg");
    if (svg) {
      svg.querySelectorAll("line").forEach((line) => {
        const lid = line.dataset.leftId;
        const rid = mapping[lid];
        const isCorrect = String(rid) === String(lid);
        line.classList.add(isCorrect ? "correct" : "incorrect");
      });
    }
  }
})();
