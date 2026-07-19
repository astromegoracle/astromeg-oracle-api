const screens = Array.from(document.querySelectorAll("[data-screen]"));
const navButtons = Array.from(document.querySelectorAll(".bottom-nav [data-go]"));
const backButton = document.querySelector("[data-back]");
const menuToggle = document.querySelector("[data-menu-toggle]");
const menuPanel = document.querySelector("#oracle-menu");
const menuScrim = document.querySelector(".menu-scrim");
const menuCloseButtons = Array.from(document.querySelectorAll("[data-menu-close]"));
const logoutButton = document.querySelector("[data-logout]");
const dailyDialog = document.querySelector("[data-daily-dialog]");
const dailyDialogClose = document.querySelector("[data-daily-dialog-close]");
const dailyDialogAsk = document.querySelector("[data-daily-dialog-ask]");
const stateKey = "astromeg-oracle-pwa-preview";
const pricingConfig = globalThis.ASTROMEG_PRICING_CONFIG || null;
const routeAliases = {
  profile: "my-chart"
};

const state = {
  history: ["start"],
  current: "start",
  profile: loadState()
};

let activeDailyPrompt = "";

const dailyPopupContent = {
  sky: {
    glyph: "☉",
    label: "Current planetary weather",
    title: "Today’s Sky",
    keywords: "Timing · momentum · decisions",
    body: "Today’s sky reveals the planetary themes shaping your timing, conversations, choices, and momentum.",
    tip: "Ask the Oracle which current transits are most active in your chart and how to work with them today."
  },
  moon: {
    glyph: "☽",
    label: "Your emotional weather",
    title: "Moon Mood",
    keywords: "Emotion · intuition · inner rhythm",
    body: "The Moon describes today’s emotional tone, instinctive needs, and the pace your inner world is asking you to honor.",
    tip: "Ask the Oracle how today’s Moon is interacting with your natal chart and what will support your peace."
  }
};

function loadState() {
  try {
    return JSON.parse(localStorage.getItem(stateKey)) || {};
  } catch {
    return {};
  }
}

function saveState() {
  localStorage.setItem(stateKey, JSON.stringify(state.profile));
}

function go(screenName, push = true) {
  screenName = routeAliases[screenName] || screenName;
  const target = screens.find((screen) => screen.dataset.screen === screenName);
  if (!target) return;

  screens.forEach((screen) => screen.classList.toggle("active", screen === target));
  navButtons.forEach((button) => button.classList.toggle("active", button.dataset.go === screenName));
  document.body.classList.toggle("onboarding-active", target.classList.contains("onboarding-screen"));

  if (push && state.current !== screenName) {
    state.history.push(screenName);
  }

  state.current = screenName;
  backButton.hidden = state.history.length <= 1;
  document.querySelector(".phone-shell").scrollTo?.({ top: 0, behavior: "instant" });
  setMenuOpen(false);
  updateProfile();
}

document.body.classList.toggle(
  "onboarding-active",
  document.querySelector("#start.onboarding-screen.active") !== null
);

function updateProfile() {
  const accessStates = Array.from(document.querySelectorAll("[data-access-state]"));
  const accessPills = Array.from(document.querySelectorAll("[data-access-pill]"));
  const accessTitle = document.querySelector("[data-access-title]");
  const accessSubtitle = document.querySelector("[data-access-subtitle]");
  const birthSummary = document.querySelector("[data-birth-summary]");
  const planetaryGuide = document.querySelector("[data-planetary-guide]");
  const access = getAccessDisplay();
  const accessPillText = getAccessPillText();

  accessStates.forEach((accessState) => {
    accessState.textContent = access.state;
  });

  accessPills.forEach((accessPill) => {
    const textTarget = accessPill.querySelector("span:last-child") || accessPill;
    textTarget.textContent = accessPillText;
  });

  if (accessTitle) accessTitle.textContent = access.title;
  if (accessSubtitle) accessSubtitle.textContent = access.subtitle;
  if (planetaryGuide) updatePlanetaryGuide(planetaryGuide);

  if (birthSummary) {
    birthSummary.textContent = state.profile.birthDate && state.profile.birthPlace
      ? `${state.profile.birthDate} · ${state.profile.birthPlace}`
      : "Not saved yet";
  }
}

function updatePlanetaryGuide(element) {
  const guides = [
    {
      weekday: "Sunday",
      glyph: "☉",
      name: "Sun",
      about: "Sunday is about visibility, vitality, and courage.",
      keywords: "Visibility, vitality, courage",
      tip: "Tip for today: Let yourself be seen and choose one action that strengthens your confidence."
    },
    {
      weekday: "Monday",
      glyph: "☾",
      name: "Moon",
      about: "Monday is about emotion, intuition, and nourishment.",
      keywords: "Emotion, intuition, nourishment",
      tip: "Tip for today: Listen to your body and make one choice that protects your peace."
    },
    {
      weekday: "Tuesday",
      glyph: "♂",
      name: "Mars",
      about: "Tuesday is about action, courage, and boundaries.",
      keywords: "Action, courage, boundaries",
      tip: "Tip for today: Take one direct step and name the boundary that keeps your energy clear."
    },
    {
      weekday: "Wednesday",
      glyph: "☿",
      name: "Mercury",
      about: "Wednesday is about messages, learning, and decisions.",
      keywords: "Messages, learning, decisions",
      tip: "Tip for today: Ask the clearer question before making your next move."
    },
    {
      weekday: "Thursday",
      glyph: "♃",
      name: "Jupiter",
      about: "Thursday is about growth, wisdom, and opportunity.",
      keywords: "Growth, wisdom, opportunity",
      tip: "Tip for today: Ask where life is inviting you to expand with more faith and clarity."
    },
    {
      weekday: "Friday",
      glyph: "♀",
      name: "Venus",
      about: "Friday is about love, beauty, money, and attraction.",
      keywords: "Love, beauty, money, attraction",
      tip: "Tip for today: Choose what feels aligned, valuable, and worth receiving."
    },
    {
      weekday: "Saturday",
      glyph: "♄",
      name: "Saturn",
      about: "Saturday is about structure, mastery, and commitment.",
      keywords: "Structure, mastery, commitment",
      tip: "Tip for today: Simplify the plan and commit to the next grounded step."
    }
  ];
  const guide = guides[new Date().getDay()];

  const label = element.querySelector("[data-guide-label]");
  const glyph = element.querySelector("[data-guide-glyph]");
  const about = element.querySelector("[data-guide-about]");
  const keywords = element.querySelector("[data-guide-keywords]");
  const tip = element.querySelector("[data-guide-tip]");

  if (label) label.textContent = `${guide.weekday} · ${guide.name}`;
  if (glyph) glyph.textContent = guide.glyph;
  if (about) about.textContent = guide.about;
  if (keywords) keywords.textContent = guide.keywords;
  if (tip) tip.textContent = guide.tip;
  element.title = guide.keywords;
  element.dataset.guideWeekday = guide.weekday;
  element.dataset.guideGlyph = guide.glyph;
  element.dataset.guideName = guide.name;
  element.dataset.guideAbout = guide.about;
  element.dataset.guideKeywords = guide.keywords;
  element.dataset.guideTip = guide.tip;
}

function openDailyDialog(button) {
  if (!dailyDialog) return;

  const type = button.dataset.dailyPopup;
  const content = type === "planet"
    ? {
        glyph: button.dataset.guideGlyph || "✦",
        label: `${button.dataset.guideWeekday || "Today"} · ${button.dataset.guideName || "Planetary guide"}`,
        title: "Today’s Planet",
        keywords: button.dataset.guideKeywords || "Daily planetary guidance",
        body: button.dataset.guideAbout || "Today’s planetary ruler offers a theme to guide your choices.",
        tip: button.dataset.guideTip || "Ask the Oracle how today’s planetary ruler speaks to your chart."
      }
    : dailyPopupContent[type];

  if (!content) return;

  dailyDialog.querySelector("[data-daily-dialog-glyph]").textContent = content.glyph;
  dailyDialog.querySelector("[data-daily-dialog-label]").textContent = content.label;
  dailyDialog.querySelector("[data-daily-dialog-title]").textContent = content.title;
  dailyDialog.querySelector("[data-daily-dialog-keywords]").textContent = content.keywords;
  dailyDialog.querySelector("[data-daily-dialog-body]").textContent = content.body;
  dailyDialog.querySelector("[data-daily-dialog-tip]").textContent = content.tip;
  activeDailyPrompt = button.dataset.fillPrompt || "";

  if (typeof dailyDialog.showModal === "function") {
    dailyDialog.showModal();
  } else {
    dailyDialog.setAttribute("open", "");
  }
}

function closeDailyDialog() {
  if (!dailyDialog) return;
  if (typeof dailyDialog.close === "function") dailyDialog.close();
  else dailyDialog.removeAttribute("open");
}

function getAccessPillText() {
  const accessEndRaw = state.profile.access_end || state.profile.accessEnd;
  const accessEnd = accessEndRaw ? new Date(accessEndRaw) : null;
  const hasValidEnd = accessEnd && !Number.isNaN(accessEnd.valueOf());

  if (hasValidEnd && accessEnd > new Date()) {
    const millisecondsPerDay = 24 * 60 * 60 * 1000;
    const daysRemaining = Math.max(1, Math.ceil((accessEnd - new Date()) / millisecondsPerDay));
    return `Oracle Access Active • ${daysRemaining} days remaining`;
  }

  return "Oracle Access Active";
}

function getAccessDisplay() {
  const accessEndRaw = state.profile.access_end || state.profile.accessEnd;
  const accessEnd = accessEndRaw ? new Date(accessEndRaw) : null;
  const hasValidEnd = accessEnd && !Number.isNaN(accessEnd.valueOf());
  const isFuture = hasValidEnd && accessEnd > new Date();
  const configuredPlanId = state.profile.plan_id || state.profile.plan;
  const configuredPlan = pricingConfig?.getPlan(configuredPlanId);
  const configuredAccountState = configuredPlan
    ? pricingConfig.evaluateAccountState({
        plan_id: configuredPlanId,
        payment_status: state.profile.payment_status || state.profile.paymentStatus,
        access_end: accessEndRaw
      })
    : null;

  if (configuredAccountState?.active) {
    return {
      title: `${configuredPlan.plan_name} Active`,
      subtitle: `Your ${configuredPlan.access_type === "full_access" ? "full" : "core"} Oracle access is active until ${formatAccessDate(accessEnd)}.`,
      state: configuredPlan.plan_name
    };
  }

  // Preserve existing legacy display behavior until a future migration is approved.
  if (state.profile.all_in_access === true && isFuture) {
    return {
      title: "VIP All-In Access Active",
      subtitle: `Everything is unlocked until ${formatAccessDate(accessEnd)}.`,
      state: "VIP All-In Access"
    };
  }

  if (state.profile.plan === "PUBLIC_CORE_MONTHLY") {
    return {
      title: "Core Access Active",
      subtitle: "Advanced readings and premium tools can be unlocked anytime.",
      state: "Core Access"
    };
  }

  if (accessEndRaw && !isFuture) {
    return {
      title: "Access Paused",
      subtitle: "Renew your Oracle access to continue.",
      state: "Access paused"
    };
  }

  return {
    title: "Access Status",
    subtitle: "Your access details will appear here.",
    state: state.profile.email ? "Access activated" : "Preview active"
  };
}

function renderPricing() {
  if (!pricingConfig) return;

  const periodLabels = {
    monthly: "/ month",
    "6_months": "/ 6 months",
    annual: "/ year"
  };

  document.querySelectorAll("[data-plan-id]").forEach((card) => {
    const plan = pricingConfig.getPlan(card.dataset.planId);
    if (!plan) return;

    const name = card.querySelector("[data-plan-name]");
    const price = card.querySelector("[data-plan-price]");
    const period = card.querySelector("[data-plan-period]");

    if (name) name.textContent = plan.plan_name;
    if (price) price.textContent = `$${plan.billing_amount}`;
    if (period) period.textContent = periodLabels[plan.billing_period] || "";
  });
}

function getInitialScreen() {
  const hash = window.location.hash.slice(1);
  const requested = routeAliases[hash] || hash;
  return screens.some((screen) => screen.dataset.screen === requested) ? requested : "start";
}

function formatAccessDate(date) {
  return new Intl.DateTimeFormat(undefined, {
    month: "long",
    day: "numeric",
    year: "numeric"
  }).format(date);
}

function setMenuOpen(isOpen) {
  if (!menuPanel || !menuToggle || !menuScrim) return;

  menuPanel.classList.toggle("open", isOpen);
  menuPanel.setAttribute("aria-hidden", String(!isOpen));
  menuToggle.setAttribute("aria-expanded", String(isOpen));
  menuScrim.hidden = !isOpen;
  document.body.classList.toggle("menu-open", isOpen);
}

function logOutPreview() {
  state.profile = {};
  state.history = ["start"];
  saveState();
  updateProfile();
  setMenuOpen(false);
  go("start", false);
}

document.addEventListener("click", (event) => {
  const dailyButton = event.target.closest("[data-daily-popup]");
  if (dailyButton) {
    openDailyDialog(dailyButton);
    return;
  }

  const button = event.target.closest("[data-go]");
  if (!button) return;

  const prompt = button.dataset.fillPrompt;
  if (prompt) {
    const questionInput = document.querySelector("[data-ask-form] input");
    if (questionInput) questionInput.value = prompt;
  }

  go(button.dataset.go);
});

dailyDialogClose?.addEventListener("click", closeDailyDialog);

dailyDialog?.addEventListener("click", (event) => {
  if (event.target === dailyDialog) closeDailyDialog();
});

dailyDialogAsk?.addEventListener("click", () => {
  const questionInput = document.querySelector("[data-ask-form] input");
  if (questionInput && activeDailyPrompt) questionInput.value = activeDailyPrompt;
  closeDailyDialog();
  go("ask");
});

menuToggle?.addEventListener("click", () => {
  const isOpen = menuPanel?.classList.contains("open");
  setMenuOpen(!isOpen);
});

menuCloseButtons.forEach((button) => {
  button.addEventListener("click", () => setMenuOpen(false));
});

logoutButton?.addEventListener("click", logOutPreview);

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") setMenuOpen(false);
});

backButton.addEventListener("click", () => {
  state.history.pop();
  const previous = state.history[state.history.length - 1] || "start";
  go(previous, false);
});

document.querySelector("[data-activate-form]").addEventListener("submit", (event) => {
  event.preventDefault();
  const form = new FormData(event.currentTarget);

  state.profile.email = form.get("email");
  state.profile.accessCode = form.get("accessCode");
  saveState();
  go("birth");
});

document.querySelector("[data-birth-form]").addEventListener("submit", (event) => {
  event.preventDefault();
  const form = new FormData(event.currentTarget);

  state.profile.birthDate = form.get("birthDate");
  state.profile.birthTime = form.get("birthTime");
  state.profile.birthPlace = form.get("birthPlace");
  saveState();
  go("home");
});

document.querySelector("[data-ask-form]").addEventListener("submit", (event) => {
  event.preventDefault();
  const input = event.currentTarget.elements.question;
  const question = input.value.trim();
  if (!question) return;

  appendMessage("You", question, "user");
  input.value = "";

  window.setTimeout(() => {
    appendMessage(
      "Astromeg Oracle",
      "I would begin by checking the natal promise, current timing, and repeating pattern around this question. The next aligned step is to name the theme clearly, choose one deliberate action, and watch the dates that confirm the movement.",
      "oracle"
    );
  }, 420);
});

function appendMessage(author, text, type) {
  const log = document.querySelector("[data-chat-log]");
  const message = document.createElement("div");
  message.className = `message ${type}`;
  message.innerHTML = `<span></span><p></p>`;
  message.querySelector("span").textContent = author;
  message.querySelector("p").textContent = text;
  log.appendChild(message);
  message.scrollIntoView({ behavior: "smooth", block: "end" });
}

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    window.scrollTo({ top: 0, left: 0, behavior: "instant" });
    navigator.serviceWorker.register("./sw.js").catch(() => {});
  });
}

if ("scrollRestoration" in window.history) {
  window.history.scrollRestoration = "manual";
}

window.scrollTo({ top: 0, left: 0, behavior: "instant" });
renderPricing();
const initialScreen = getInitialScreen();
state.history = [initialScreen];
go(initialScreen, false);
