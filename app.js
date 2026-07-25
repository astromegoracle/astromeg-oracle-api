const screens = Array.from(document.querySelectorAll("[data-screen]"));
document.documentElement.dataset.oracleChatVersion = "onboarding-code-v2";
const navButtons = Array.from(document.querySelectorAll(".bottom-nav [data-go]"));
const backButton = document.querySelector("[data-back]");
const menuToggle = document.querySelector("[data-menu-toggle]");
const menuPanel = document.querySelector("#oracle-menu");
const menuScrim = document.querySelector(".menu-scrim");
const menuCloseButtons = Array.from(document.querySelectorAll("[data-menu-close]"));
const logoutButton = document.querySelector("[data-logout]");
const onboardingSlides = Array.from(document.querySelectorAll("[data-onboarding-slide]"));
const onboardingDots = Array.from(document.querySelectorAll("[data-onboarding-dot]"));
const onboardingNextButton = document.querySelector("[data-onboarding-next]");
const dailyDialog = document.querySelector("[data-daily-dialog]");
const dailyDialogClose = document.querySelector("[data-daily-dialog-close]");
const dailyDialogAsk = document.querySelector("[data-daily-dialog-ask]");
const lessonDialog = document.querySelector("[data-lesson-dialog]");
const lessonDialogClose = document.querySelector("[data-lesson-dialog-close]");
const beginLessonButton = document.querySelector("[data-begin-lesson]");
const saveReadingDialog = document.querySelector("[data-save-reading-dialog]");
const saveReadingForm = document.querySelector("[data-save-reading-form]");
const saveReadingClose = document.querySelector("[data-save-reading-close]");
const saveReadingCategory = document.querySelector("[data-save-reading-category]");
const customCategoryWrap = document.querySelector("[data-custom-category-wrap]");
const customCategoryInput = document.querySelector("[data-custom-category-input]");
const saveReadingPreview = document.querySelector("[data-save-reading-preview]");
const unlockReadingDialog = document.querySelector("[data-unlock-reading-dialog]");
const unlockReadingTitle = document.querySelector("[data-unlock-reading-title]");
const unlockReadingPurpose = document.querySelector("[data-unlock-reading-purpose]");
const unlockReadingCurrentAccess = document.querySelector("[data-unlock-reading-current-access]");
const unlockReadingRequiredAccess = document.querySelector("[data-unlock-reading-required-access]");
const unlockReadingAction = document.querySelector("[data-unlock-reading-action]");
const accessCodeDialog = document.querySelector("[data-access-code-dialog]");
const accessCodeForm = document.querySelector("[data-access-code-form]");
const accessCodeStatus = document.querySelector("[data-access-code-status]");
const savedReadingViewer = document.querySelector("[data-saved-reading-viewer]");
const savedReadingViewerClose = document.querySelector("[data-saved-reading-viewer-close]");
const savedReadingViewerInner = document.querySelector(".saved-reading-viewer-inner");
const savedReadingViewerCategory = document.querySelector("[data-saved-reading-viewer-category]");
const savedReadingViewerTitle = document.querySelector("[data-saved-reading-viewer-title]");
const savedReadingViewerQuestion = document.querySelector("[data-saved-reading-viewer-question]");
const savedReadingViewerDate = document.querySelector("[data-saved-reading-viewer-date]");
const savedReadingViewerContent = document.querySelector("[data-saved-reading-viewer-content]");
const personChartDialog = document.querySelector("[data-person-chart-dialog]");
const personChartClose = document.querySelector("[data-person-chart-close]");
const journalForm = document.querySelector("[data-journal-form]");
const saveToast = document.querySelector("[data-save-toast]");
const stateKey = "astromeg-oracle-pwa-preview";
const pricingConfig = globalThis.ASTROMEG_PRICING_CONFIG || null;
const checkoutEmailInput = document.querySelector("[data-checkout-email]");
const checkoutStatus = document.querySelector("[data-checkout-status]");
const googleButtonHost = document.querySelector("[data-google-button]");
const googleSignInFallback = document.querySelector("[data-google-signin-fallback]");
const signInStatus = document.querySelector("[data-signin-status]");
const emailSignInStatus = document.querySelector("[data-email-signin-status]");
const themeButtons = Array.from(document.querySelectorAll("[data-theme-choice]"));
const themeToggleButton = document.querySelector("[data-theme-toggle]");
const themeToggleLabel = document.querySelector("[data-theme-toggle-label]");
const todaySkyNotificationStatus = document.querySelector("[data-today-sky-notification-status]");
const todaySkyNotificationToggle = document.querySelector("[data-today-sky-notification-toggle]");
const todaySkyNotificationLabel = document.querySelector("[data-today-sky-notification-label]");
const backendBaseUrl = String(globalThis.ASTROMEG_BACKEND_BASE_URL || "https://astromeg-oracle-api.onrender.com").replace(/\/$/, "");
const checkoutEndpoint = globalThis.ASTROMEG_CHECKOUT_ENDPOINT || `${backendBaseUrl}/create-checkout-session`;
const googleAuthConfigEndpoint = globalThis.ASTROMEG_GOOGLE_AUTH_CONFIG_ENDPOINT || `${backendBaseUrl}/auth/google/config`;
const googleAuthEndpoint = globalThis.ASTROMEG_GOOGLE_AUTH_ENDPOINT || `${backendBaseUrl}/auth/google`;
const emailAuthEndpoint = globalThis.ASTROMEG_EMAIL_AUTH_ENDPOINT || `${backendBaseUrl}/auth/email`;
const accessCodeAuthEndpoint = globalThis.ASTROMEG_ACCESS_CODE_AUTH_ENDPOINT || `${backendBaseUrl}/auth/access-code`;
const oracleChatEndpoint = globalThis.ASTROMEG_ORACLE_CHAT_ENDPOINT || `${backendBaseUrl}/oracle/chat`;
const oracleOwnerEmails = new Set(["meg.sanchez@gmail.com"]);
const themeKey = `${stateKey}-theme`;
const todaySkyNotificationKey = `${stateKey}-today-sky-notifications`;
const previewHostname = window.location.hostname;
const isLocalNotificationPreview =
  ["127.0.0.1", "localhost", "::1"].includes(previewHostname) ||
  /^10\./.test(previewHostname) ||
  /^192\.168\./.test(previewHostname) ||
  /^172\.(1[6-9]|2\d|3[01])\./.test(previewHostname);
const routeAliases = {
  profile: "my-chart"
};

const state = {
  history: ["start"],
  current: "start",
  chatMode: "default",
  profile: loadState()
};

let activeDailyPrompt = "";
let activeZodiacIndex = 0;
let activeMeditationIndex = 0;
let activeOnboardingSlide = 0;
let activeReadingDraft = null;
let activeLockedReading = null;
let activeLessonLevel = "";
let saveToastTimer = 0;
let googleIdentityScriptPromise = null;

const customCategoryValue = "__custom__";
const defaultReadingCategories = [
  {
    name: "Year-Ahead Alignment",
    title: "Career, money, and visibility themes",
    body: "Ready to save as a PDF reading in the app version."
  },
  {
    name: "Relationship Pattern",
    title: "Repeating cycles and next-step clarity",
    body: "Return to this when the same lesson shows up again."
  },
  {
    name: "Timing Window",
    title: "Launch, pause, or prepare",
    body: "Use dates and chart weather to move deliberately."
  },
  {
    name: "Karma & Healing",
    title: "Saturn lessons and inner child healing",
    body: "Save karmic themes, soul mastery, and wounding readings here."
  }
];
const readingDrafts = new Map();

const lessonLevels = {
  basic: {
    label: "Basic",
    title: "Basic Lesson",
    body: "Start with the language of signs, planets, houses, and the birth chart foundation."
  },
  intermediate: {
    label: "Intermediate",
    title: "Intermediate Lesson",
    body: "Build interpretation skills with aspects, timing, patterns, and chart synthesis."
  },
  advanced: {
    label: "Advanced",
    title: "Advanced Lesson",
    body: "Enter predictive timing, karmic signatures, relationship dynamics, and deeper chart mastery."
  }
};

const oracleReadingCatalog = [
  {
    tier: "essential",
    tierLabel: "Oracle Essential",
    title: "In-Depth Natal Chart",
    purpose: "Your planets, signs, houses, degrees, aspects, and chart balance.",
    prompt: "Calculate my in-depth natal chart with exact planets, signs, houses, degrees, aspects, and chart balance."
  },
  {
    tier: "essential",
    tierLabel: "Oracle Essential",
    title: "Transit Timeline",
    purpose: "Exact current and upcoming transits for timing decisions and turning points.",
    prompt: "Calculate my exact transit timeline and explain the dates and turning points I should watch."
  },
  {
    tier: "essential",
    tierLabel: "Oracle Essential",
    title: "Solar Return",
    purpose: "Your birthday-to-birthday themes, placements, houses, and yearly focus.",
    prompt: "Calculate my exact Solar Return chart with planets, degrees, houses, and major themes."
  },
  {
    tier: "essential",
    tierLabel: "Oracle Essential",
    title: "Secondary Progressed Chart",
    purpose: "Your inner development, emotional season, and unfolding life chapter.",
    prompt: "Calculate my Secondary Progressed chart and explain my current inner development and life chapter."
  },
  {
    tier: "essential",
    tierLabel: "Oracle Essential",
    title: "Solar Arc Directions",
    purpose: "Directed planets and angles for major events and life developments.",
    prompt: "Calculate my Solar Arc Directions with exact directed planets, angles, degrees, houses, and timing themes."
  },
  {
    tier: "essential",
    tierLabel: "Oracle Essential",
    title: "Love & Relationship Patterns",
    purpose: "Relationship dynamics, repeating patterns, love timing, and partner insight.",
    prompt: "Give me an in-depth Love and Relationship Patterns reading based on my chart."
  },
  {
    tier: "essential",
    tierLabel: "Oracle Essential",
    title: "Money & Career Guidance",
    purpose: "Wealth potential, career direction, success strategy, and money blocks.",
    prompt: "Give me an in-depth Money and Career reading based on my chart and current timing."
  },
  {
    tier: "essential",
    tierLabel: "Oracle Essential",
    title: "Karma & Healing",
    purpose: "Saturn lessons, soul mastery, inner-child themes, and healing patterns.",
    prompt: "Give me an in-depth Karma and Healing reading based on my chart."
  },
  {
    tier: "essential_annual",
    tierLabel: "Essential Annual Love Suite",
    title: "Synastry",
    purpose: "How two birth charts interact, attract, challenge, and support each other.",
    prompt: "Calculate a Synastry relationship reading for me and a saved person."
  },
  {
    tier: "essential_annual",
    tierLabel: "Essential Annual Love Suite",
    title: "Composite Relationship Chart",
    purpose: "The relationship itself as a third chart, with its shared purpose and patterns.",
    prompt: "Calculate our exact Composite Relationship chart and interpret its shared purpose and patterns."
  },
  {
    tier: "essential_annual",
    tierLabel: "Essential Annual Love Suite",
    title: "Davison Relationship Chart",
    purpose: "A time-and-space midpoint chart for the relationship's lived story.",
    prompt: "Calculate our exact Davison Relationship chart and interpret its timing and lived story."
  },
  {
    tier: "all_access",
    tierLabel: "Oracle All Access",
    title: "Draconic Soul Path",
    purpose: "Soul-level themes, karmic memory, and deeper purpose.",
    prompt: "Give me an in-depth Draconic Soul Path reading."
  },
  {
    tier: "all_access",
    tierLabel: "Oracle All Access",
    title: "Firdaria Time Lords",
    purpose: "The planetary ruler of your current life period and its agenda.",
    prompt: "Calculate my Firdaria Time Lords and explain my current planetary period."
  },
  {
    tier: "all_access",
    tierLabel: "Oracle All Access",
    title: "Hellenistic Annual Profection",
    purpose: "Your activated house, time lord, and themes for the year.",
    prompt: "Calculate my Hellenistic Annual Profection and interpret my activated house and time lord."
  },
  {
    tier: "all_access",
    tierLabel: "Oracle All Access",
    title: "Horary",
    purpose: "A chart for one precise question at the moment it is asked.",
    prompt: "Cast an exact Horary chart for my question and interpret the answer."
  },
  {
    tier: "all_access",
    tierLabel: "Oracle All Access",
    title: "Electional Timing",
    purpose: "Choose the most supportive date and time for an important action.",
    prompt: "Find the best Electional date and time for my specific goal."
  },
  {
    tier: "all_access",
    tierLabel: "Oracle All Access",
    title: "Harmonic Deep Dive",
    purpose: "Specialized harmonic patterns that reveal subtle talents and themes.",
    prompt: "Calculate my Harmonic charts and give me a deeper look at the strongest patterns."
  },
  {
    tier: "all_access",
    tierLabel: "Oracle All Access",
    title: "Fixed Stars",
    purpose: "Prominent stellar conjunctions and their influence in your chart.",
    prompt: "Analyze the important Fixed Stars in my chart and explain their influence."
  },
  {
    tier: "all_access_annual",
    tierLabel: "All Access Annual",
    title: "Arabic Parts (Lots)",
    purpose: "Traditional calculated points for fortune, spirit, purpose, and key life topics.",
    prompt: "Calculate my Arabic Parts or Lots and interpret the most important points."
  }
];

const defaultNatalPlacements = [
  { glyph: "☉", body: "Sun", sign: "Leo", house: "10th", degree: "26°14′" },
  { glyph: "☽", body: "Moon", sign: "Pisces", house: "5th", degree: "11°02′" },
  { glyph: "☿", body: "Mercury", sign: "Virgo", house: "11th", degree: "03°47′" },
  { glyph: "♀", body: "Venus", sign: "Cancer", house: "9th", degree: "18°36′" },
  { glyph: "♂", body: "Mars", sign: "Libra", house: "12th", degree: "07°25′" },
  { glyph: "♃", body: "Jupiter", sign: "Sagittarius", house: "2nd", degree: "21°09′" },
  { glyph: "♄", body: "Saturn", sign: "Capricorn", house: "3rd", degree: "14°58′" },
  { glyph: "♅", body: "Uranus", sign: "Capricorn", house: "3rd", degree: "05°41′" },
  { glyph: "♆", body: "Neptune", sign: "Capricorn", house: "3rd", degree: "12°17′" },
  { glyph: "♇", body: "Pluto", sign: "Scorpio", house: "1st", degree: "15°52′" },
  { glyph: "☊", body: "North Node", sign: "Aquarius", house: "4th", degree: "22°34′" },
  { glyph: "⚷", body: "Chiron", sign: "Cancer", house: "9th", degree: "09°19′" },
  { glyph: "AC", body: "Ascendant", sign: "Scorpio", house: "1st", degree: "02°43′" },
  { glyph: "MC", body: "Midheaven", sign: "Leo", house: "10th", degree: "08°31′" }
];

const defaultNatalAspects = [
  { first: "Sun", aspect: "trine", second: "Jupiter", orb: "1°12′" },
  { first: "Moon", aspect: "trine", second: "Venus", orb: "2°26′" },
  { first: "Mercury", aspect: "trine", second: "Saturn", orb: "3°04′" },
  { first: "Venus", aspect: "opposition", second: "Neptune", orb: "1°41′" },
  { first: "Mars", aspect: "square", second: "Saturn", orb: "2°18′" },
  { first: "Pluto", aspect: "conjunct", second: "Ascendant", orb: "4°09′" }
];

const defaultChartBalance = {
  elements: "Fire 4 · Earth 4 · Air 2 · Water 4",
  modality: "Cardinal 5 · Fixed 4 · Mutable 5",
  dominantElement: "Fire + Earth",
  dominantModality: "Cardinal",
  sectNote: "Based on stored birth time"
};

const moonMarsChallenges = [
  {
    aspect: "Moon conjunct Mars",
    copy: "Feel the heat before you act. Your challenge is to move with courage without rushing the emotional truth.",
    prompt: "How should I work with a Moon conjunct Mars challenge today?"
  },
  {
    aspect: "Moon sextile Mars",
    copy: "Use momentum gently. Your challenge is to take one brave action while keeping your nervous system steady.",
    prompt: "How should I use today’s Moon sextile Mars energy?"
  },
  {
    aspect: "Moon square Mars",
    copy: "Pause before reacting. Your challenge is to turn irritation into one clean boundary or focused action.",
    prompt: "How should I handle today’s Moon square Mars challenge?"
  },
  {
    aspect: "Moon trine Mars",
    copy: "Trust your instinct and move. Your challenge is to act on what your body already knows.",
    prompt: "What aligned action should I take under today’s Moon trine Mars energy?"
  },
  {
    aspect: "Moon opposite Mars",
    copy: "Do not let urgency choose for you. Your challenge is to balance your needs with someone else’s fire.",
    prompt: "How should I work with today’s Moon opposite Mars tension?"
  }
];

const zodiacPlaylists = [
  {
    id: "aries",
    name: "Aries",
    glyph: "♈",
    meta: "Fire · Cardinal",
    image: "./assets/zodiac-playlist-aries.jpeg",
    url: "https://soundcloud.com/prismatechai/sets/aries-soundtrack",
    theme: "Bold starts, brave desire, and clean momentum.",
    tones: ["Energy", "Courage", "Action"],
    note: "Begin before the doubt gets a vote.",
    prompt: "What Aries part of me needs courage, action, and a clean new beginning?"
  },
  {
    id: "taurus",
    name: "Taurus",
    glyph: "♉",
    meta: "Earth · Fixed",
    image: "./assets/zodiac-playlist-taurus.jpeg",
    url: "https://soundcloud.com/prismatechai/sets/taurus-soundtrack",
    theme: "Soft luxury, self-worth, and nervous-system calm.",
    tones: ["Worth", "Pleasure", "Grounding"],
    note: "Let desire become simple, steady, and real.",
    prompt: "What Taurus lesson is teaching me worth, stability, and receiving right now?"
  },
  {
    id: "gemini",
    name: "Gemini",
    glyph: "♊",
    meta: "Air · Mutable",
    image: "./assets/zodiac-playlist-gemini.jpeg",
    url: "https://soundcloud.com/prismatechai/sets/gemini-soundtrack",
    theme: "Curiosity, clever turns, and messages in motion.",
    tones: ["Ideas", "Voice", "Movement"],
    note: "Follow the question that makes your mind sparkle.",
    prompt: "What Gemini message, idea, or conversation should I pay attention to?"
  },
  {
    id: "cancer",
    name: "Cancer",
    glyph: "♋",
    meta: "Water · Cardinal",
    image: "./assets/zodiac-playlist-cancer.jpeg",
    url: "https://soundcloud.com/prismatechai/sets/cancer-soundtrack",
    theme: "Moonlit memory, protection, and emotional truth.",
    tones: ["Feeling", "Home", "Care"],
    note: "Your sensitivity is a compass, not a problem.",
    prompt: "What Cancer emotional pattern needs care, protection, or healing?"
  },
  {
    id: "leo",
    name: "Leo",
    glyph: "♌",
    meta: "Fire · Fixed",
    image: "./assets/zodiac-playlist-leo.jpeg",
    url: "https://soundcloud.com/prismatechai/sets/leo-soundtrack",
    theme: "Radiance, confidence, and unapologetic heart.",
    tones: ["Glow", "Heart", "Creation"],
    note: "Let your joy take up visible space.",
    prompt: "Where is Leo asking me to be visible, creative, and brave-hearted?"
  },
  {
    id: "virgo",
    name: "Virgo",
    glyph: "♍",
    meta: "Earth · Mutable",
    image: "./assets/zodiac-playlist-virgo.jpeg",
    url: "https://soundcloud.com/prismatechai/sets/virgo-soundtrack",
    theme: "Ritual, refinement, and the magic of small steps.",
    tones: ["Ritual", "Clarity", "Craft"],
    note: "The sacred is already inside the details.",
    prompt: "What Virgo detail, habit, or ritual will help me align my life?"
  },
  {
    id: "libra",
    name: "Libra",
    glyph: "♎",
    meta: "Air · Cardinal",
    image: "./assets/zodiac-playlist-libra.jpeg",
    url: "https://soundcloud.com/prismatechai/sets/libra-soundtrack",
    theme: "Beauty, balance, and the art of choosing harmony.",
    tones: ["Beauty", "Love", "Balance"],
    note: "Peace is also something you are allowed to choose.",
    prompt: "What Libra lesson is showing up in love, balance, beauty, or choice?"
  },
  {
    id: "scorpio",
    name: "Scorpio",
    glyph: "♏",
    meta: "Water · Fixed",
    image: "./assets/zodiac-playlist-scorpio.jpeg",
    url: "https://soundcloud.com/prismatechai/sets/scorpio-playlist",
    theme: "Depth, release, magnetism, and shadow alchemy.",
    tones: ["Depth", "Power", "Release"],
    note: "Transformation starts where you stop pretending.",
    prompt: "What Scorpio shadow, truth, or transformation is asking for my attention?"
  },
  {
    id: "sagittarius",
    name: "Sagittarius",
    glyph: "♐",
    meta: "Fire · Mutable",
    image: "./assets/zodiac-playlist-sagittarius.jpeg",
    url: "https://soundcloud.com/prismatechai/sets/sagittarius-soundtrack",
    theme: "Freedom, faith, big vision, and open-road wisdom.",
    tones: ["Freedom", "Faith", "Vision"],
    note: "Aim toward the life that makes your spirit wider.",
    prompt: "What Sagittarius vision, belief, or adventure is calling me forward?"
  },
  {
    id: "capricorn",
    name: "Capricorn",
    glyph: "♑",
    meta: "Earth · Cardinal",
    image: "./assets/zodiac-playlist-capricorn.jpeg",
    url: "https://soundcloud.com/prismatechai/sets/capricorn-soundtrack",
    theme: "Discipline, devotion, and long-range destiny.",
    tones: ["Mastery", "Legacy", "Focus"],
    note: "Build the version of your life that can hold your future.",
    prompt: "What Capricorn structure, boundary, or long-term goal needs my focus?"
  },
  {
    id: "aquarius",
    name: "Aquarius",
    glyph: "♒",
    meta: "Air · Fixed",
    image: "./assets/zodiac-playlist-aquarius.jpeg",
    url: "https://soundcloud.com/prismatechai/sets/aquarius-soundtrack",
    theme: "Future frequency, originality, and liberated thinking.",
    tones: ["Future", "Vision", "Freedom"],
    note: "Your difference is part of the signal.",
    prompt: "What Aquarius insight is helping me break patterns and think differently?"
  },
  {
    id: "pisces",
    name: "Pisces",
    glyph: "♓",
    meta: "Water · Mutable",
    image: "./assets/zodiac-playlist-pisces.jpeg",
    url: "https://soundcloud.com/prismatechai/sets/pisces-soundtrack",
    theme: "Dreams, devotion, mysticism, and emotional surrender.",
    tones: ["Dreams", "Spirit", "Surrender"],
    note: "Let intuition soften what force cannot solve.",
    prompt: "What Pisces dream, intuition, or spiritual message should I trust?"
  }
];

const meditationPlaylists = [
  {
    id: "healing",
    name: "Healing",
    glyph: "✦",
    meta: "Healing · nervous system reset",
    url: "https://soundcloud.com/prismatechai/sets/guided-meditation-healing",
    banner: "./assets/guided-meditation-banner-healing.mp4",
    copy: "Return to your center with a soft clearing practice for emotional repair and energetic release."
  },
  {
    id: "wealth",
    name: "Wealth",
    glyph: "◇",
    meta: "Wealth · receiving practice",
    url: "https://soundcloud.com/prismatechai/sets/manifestation-guided",
    banner: "./assets/guided-meditation-banner-wealth.mp4",
    copy: "Open the field for prosperity, self-worth, and aligned manifestation without leaving your body behind."
  },
  {
    id: "vipassana",
    name: "Vipassana",
    glyph: "◠",
    meta: "Vipassana · mindful observation",
    url: "https://soundcloud.com/prismatechai/sets/vipassana-introduction",
    banner: "./assets/guided-meditation-banner-vipassana.mp4",
    copy: "Slow down, observe clearly, and come back to the quiet intelligence underneath the noise."
  },
  {
    id: "relationship",
    name: "Relationship",
    glyph: "♡",
    meta: "Relationship · heart alignment",
    url: "https://soundcloud.com/prismatechai/sets/guided-meditation-manifest-a",
    banner: "./assets/guided-meditation-banner-relationship.mp4",
    copy: "Soften the heart field and reconnect with love, desire, attachment, and emotional truth."
  }
];

const meditationRoutes = {
  "meditation-healing": "healing",
  "meditation-wealth": "wealth",
  "meditation-vipassana": "vipassana",
  "meditation-relationship": "relationship"
};

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

function getUrlThemePreference() {
  const theme = new URLSearchParams(window.location.search).get("theme");
  return theme === "dark" || theme === "light" ? theme : "";
}

function loadThemePreference() {
  const urlTheme = getUrlThemePreference();
  if (urlTheme) return urlTheme;
  return localStorage.getItem(themeKey) === "dark" ? "dark" : "light";
}

function setThemePreference(theme, persist = true) {
  const nextTheme = theme === "dark" ? "dark" : "light";
  const isDark = nextTheme === "dark";
  const themeColor = isDark ? "#171020" : "#f6eaf2";
  const metaThemeColor = document.querySelector('meta[name="theme-color"]');

  document.body.classList.toggle("theme-dark", isDark);
  document.documentElement.dataset.theme = nextTheme;
  metaThemeColor?.setAttribute("content", themeColor);

  themeButtons.forEach((button) => {
    const isActive = button.dataset.themeChoice === nextTheme;
    button.classList.toggle("active", isActive);
    button.setAttribute("aria-pressed", String(isActive));
  });

  if (themeToggleButton) {
    themeToggleButton.setAttribute("aria-pressed", String(isDark));
  }

  if (themeToggleLabel) {
    themeToggleLabel.textContent = isDark ? "Tap to return to light mode" : "Tap to turn dark mode on";
  }

  if (persist) localStorage.setItem(themeKey, nextTheme);
}

function toggleThemePreference() {
  setThemePreference(document.documentElement.dataset.theme === "dark" ? "light" : "dark");
}

function syncTodaySkyNotificationToggle() {
  const isSupported = "Notification" in window && "serviceWorker" in navigator;
  const wantsNotifications = localStorage.getItem(todaySkyNotificationKey) === "enabled";
  const isEnabled = wantsNotifications && (
    isLocalNotificationPreview ||
    (isSupported && Notification.permission === "granted")
  );

  if (todaySkyNotificationToggle) {
    todaySkyNotificationToggle.setAttribute("aria-checked", String(isEnabled));
    todaySkyNotificationToggle.disabled = false;
    todaySkyNotificationToggle.setAttribute("aria-disabled", "false");
    todaySkyNotificationToggle.dataset.notificationState = isEnabled ? "on" : "off";
  }

  if (todaySkyNotificationLabel) {
    todaySkyNotificationLabel.textContent = isEnabled ? "On" : "Off";
  }

  return isEnabled;
}

function updateTodaySkyNotificationStatus(message = "") {
  const isEnabled = syncTodaySkyNotificationToggle();
  if (!todaySkyNotificationStatus) return;

  if (message) {
    todaySkyNotificationStatus.textContent = message;
    return;
  }

  if (isLocalNotificationPreview) {
    todaySkyNotificationStatus.textContent = isEnabled
      ? "Today’s Sky notifications are enabled in this preview."
      : "Turn on daily reminders.";
    return;
  }

  if (!("Notification" in window)) {
    todaySkyNotificationStatus.textContent = "Open the installed Astromeg app to enable notifications on this device.";
    return;
  }

  if (!("serviceWorker" in navigator)) {
    todaySkyNotificationStatus.textContent = "Open the installed Astromeg app to enable notifications on this device.";
    return;
  }

  if (Notification.permission === "granted") {
    todaySkyNotificationStatus.textContent = isEnabled
      ? "Today’s Sky notifications are enabled for this device."
      : "Today’s Sky notifications are paused on this device.";
    return;
  }

  if (Notification.permission === "denied") {
    todaySkyNotificationStatus.textContent = "Notifications were previously blocked on this device.";
    return;
  }

  todaySkyNotificationStatus.textContent = "Turn this on once. Your phone will ask you to allow notifications.";
}

function requestNotificationPermission() {
  const permissionRequest = Notification.requestPermission();
  if (permissionRequest && typeof permissionRequest.then === "function") {
    return permissionRequest;
  }

  return Promise.resolve(Notification.permission);
}

async function enableTodaySkyNotifications() {
  if (isLocalNotificationPreview) {
    localStorage.setItem(todaySkyNotificationKey, "enabled");
    updateTodaySkyNotificationStatus("Today’s Sky notifications are enabled in this preview.");
    return;
  }

  if (!("Notification" in window)) {
    updateTodaySkyNotificationStatus("This browser does not support app notifications yet.");
    return;
  }

  if (!("serviceWorker" in navigator)) {
    updateTodaySkyNotificationStatus("Notifications need the PWA service worker to be available.");
    return;
  }

  if (Notification.permission === "denied") {
    localStorage.setItem(todaySkyNotificationKey, "disabled");
    updateTodaySkyNotificationStatus("Notifications were previously blocked on this device.");
    return;
  }

  try {
    const permission = Notification.permission === "granted"
      ? "granted"
      : await requestNotificationPermission();

    if (permission !== "granted") {
      localStorage.setItem(todaySkyNotificationKey, "disabled");
      updateTodaySkyNotificationStatus("Notifications remain off on this device.");
      return;
    }

    localStorage.setItem(todaySkyNotificationKey, "enabled");
    updateTodaySkyNotificationStatus("Today’s Sky notifications are enabled for this device.");
  } catch {
    updateTodaySkyNotificationStatus("I could not enable notifications in this browser.");
  }
}

async function toggleTodaySkyNotifications() {
  if (syncTodaySkyNotificationToggle()) {
    localStorage.setItem(todaySkyNotificationKey, "disabled");
    updateTodaySkyNotificationStatus("Today’s Sky notifications are paused on this device.");
    return;
  }

  await enableTodaySkyNotifications();
}

function go(screenName, push = true, routeName = "") {
  const routeInfo = getRouteInfo(screenName);
  screenName = routeInfo.screen;
  routeName = routeName || routeInfo.route;
  const target = screens.find((screen) => screen.dataset.screen === screenName);
  if (!target) return;

  screens.forEach((screen) => screen.classList.toggle("active", screen === target));
  navButtons.forEach((button) => button.classList.toggle("active", button.dataset.go === screenName));
  document.body.classList.toggle("onboarding-active", target.classList.contains("onboarding-screen"));
  document.body.dataset.cosmicScreen = screenName;

  if (push && state.current !== screenName) {
    state.history.push(screenName);
  }

  syncRoute(routeName, push);
  state.current = screenName;
  backButton.hidden = state.history.length <= 1;
  resetAppScroll(target);
  setMenuOpen(false);
  updateProfile();
  updateAskWelcome();
  updateTodaySkyNotificationStatus();

  if (screenName === "start") {
    setOnboardingSlide(0);
  }
}

function resetAppScroll(target = document.querySelector(".screen.active")) {
  const scrollTargets = [
    window,
    document.scrollingElement,
    document.documentElement,
    document.body,
    document.querySelector(".phone-shell"),
    target
  ].filter(Boolean);

  const reset = () => {
    scrollTargets.forEach((scrollTarget) => {
      if (scrollTarget === window) {
        window.scrollTo({ top: 0, left: 0, behavior: "auto" });
        return;
      }

      scrollTarget.scrollTop = 0;
      scrollTarget.scrollLeft = 0;
      scrollTarget.scrollTo?.({ top: 0, left: 0, behavior: "auto" });
    });
  };

  reset();
  requestAnimationFrame(reset);
  window.setTimeout(reset, 80);
}

document.body.classList.toggle(
  "onboarding-active",
  document.querySelector("#start.onboarding-screen.active") !== null
);

function setOnboardingSlide(index) {
  if (!onboardingSlides.length) return;

  const lastIndex = onboardingSlides.length - 1;
  activeOnboardingSlide = Math.max(0, Math.min(index, lastIndex));

  onboardingSlides.forEach((slide, slideIndex) => {
    const isActive = slideIndex === activeOnboardingSlide;
    slide.classList.toggle("is-active", isActive);
    slide.setAttribute("aria-hidden", String(!isActive));
  });

  onboardingDots.forEach((dot, dotIndex) => {
    const isActive = dotIndex === activeOnboardingSlide;
    dot.classList.toggle("is-active", isActive);
    if (isActive) {
      dot.setAttribute("aria-current", "step");
    } else {
      dot.removeAttribute("aria-current");
    }
  });

  if (onboardingNextButton) {
    onboardingNextButton.textContent = activeOnboardingSlide === lastIndex ? "Sign In" : "Next";
  }
}

function advanceOnboarding() {
  if (!onboardingSlides.length) {
    go("activate");
    return;
  }

  if (activeOnboardingSlide >= onboardingSlides.length - 1) {
    go("activate");
    return;
  }

  setOnboardingSlide(activeOnboardingSlide + 1);
}

function updateProfile() {
  const accessStates = Array.from(document.querySelectorAll("[data-access-state]"));
  const accessPills = Array.from(document.querySelectorAll("[data-access-pill]"));
  const accessTitle = document.querySelector("[data-access-title]");
  const accessSubtitle = document.querySelector("[data-access-subtitle]");
  const birthSummaries = Array.from(document.querySelectorAll("[data-birth-summary]"));
  const planetaryGuide = document.querySelector("[data-planetary-guide]");
  const access = getAccessDisplay();
  const accessPillState = getAccessPillState();

  accessStates.forEach((accessState) => {
    accessState.textContent = access.state;
  });

  accessPills.forEach((accessPill) => {
    const textTarget = accessPill.querySelector("[data-access-text]") || accessPill.querySelector("span:last-child") || accessPill;
    const iconTarget = accessPill.querySelector("[data-access-icon]");
    textTarget.textContent = accessPillState.text;
    if (iconTarget) iconTarget.textContent = accessPillState.icon;
    accessPill.classList.toggle("inactive", !accessPillState.active);
    accessPill.setAttribute("aria-label", accessPillState.text);
  });

  if (accessTitle) accessTitle.textContent = access.title;
  if (accessSubtitle) accessSubtitle.textContent = access.subtitle;
  if (planetaryGuide) updatePlanetaryGuide(planetaryGuide);
  if (checkoutEmailInput && state.profile.email && !checkoutEmailInput.value) {
    checkoutEmailInput.value = state.profile.email;
  }

  birthSummaries.forEach((birthSummary) => {
    birthSummary.textContent = getBirthSummary();
  });

  renderChartVault();
  renderJournal();
  renderDailyChallenge();
  renderSavedReadings();
  updateAskWelcome();
}

function getBirthCity() {
  if (state.profile.birthCity) return String(state.profile.birthCity);
  const place = String(state.profile.birthPlace || "");
  return place.split(",")[0]?.trim() || "";
}

function getBirthCountry() {
  if (state.profile.birthCountry) return String(state.profile.birthCountry);
  const place = String(state.profile.birthPlace || "");
  const parts = place.split(",");
  return parts.length > 1 ? parts.slice(1).join(",").trim() : "";
}

function getBirthPlace() {
  const city = getBirthCity();
  const country = getBirthCountry();
  return [city, country].filter(Boolean).join(", ");
}

function getBirthSummary() {
  const parts = [
    state.profile.birthDate,
    state.profile.birthTime,
    getBirthPlace()
  ].filter(Boolean);

  return parts.length ? parts.join(" · ") : "Not saved yet";
}

function renderDailyChallenge() {
  const challenge = getDailyChallengePreview(new Date());
  const aspect = document.querySelector("[data-challenge-aspect]");
  const copy = document.querySelector("[data-challenge-copy]");
  const prompt = document.querySelector("[data-challenge-prompt]");

  if (aspect) aspect.textContent = challenge.aspect;
  if (copy) copy.textContent = challenge.copy;
  if (prompt) prompt.dataset.fillPrompt = challenge.prompt;
}

function getDailyChallengePreview(date) {
  const startOfYear = new Date(date.getFullYear(), 0, 0);
  const dayOfYear = Math.floor((date - startOfYear) / 86400000);
  return moonMarsChallenges[dayOfYear % moonMarsChallenges.length];
}

function renderChartVault() {
  renderChartProfile();
  renderPlacements();
  renderAspects();
  renderChartBalance();
  renderSavedPeople();
}

function renderChartProfile() {
  const clientName = document.querySelector("[data-chart-client-name]");
  const sectPill = document.querySelector("[data-chart-sect-pill]");
  const form = document.querySelector("[data-chart-profile-form]");
  const shouldFillForm = form && !form.contains(document.activeElement);

  if (clientName) clientName.textContent = state.profile.name || "Your Name";
  if (sectPill) sectPill.textContent = getChartSect();

  if (!shouldFillForm) return;

  const fields = {
    "[data-profile-name]": state.profile.name || "",
    "[data-profile-birth-date]": state.profile.birthDate || "",
    "[data-profile-birth-time]": state.profile.birthTime || "",
    "[data-profile-birth-city]": getBirthCity(),
    "[data-profile-birth-country]": getBirthCountry()
  };

  Object.entries(fields).forEach(([selector, value]) => {
    const field = form.querySelector(selector);
    if (field) field.value = value;
  });
}

function getChartSect() {
  const storedSect = state.profile.chart?.sect || state.profile.chartSect;
  if (storedSect) return String(storedSect);

  const birthTime = state.profile.birthTime;
  if (!birthTime) return "Day / Night";

  const hour = Number(String(birthTime).split(":")[0]);
  return hour >= 6 && hour < 18 ? "Day Chart" : "Night Chart";
}

function getNatalPlacements() {
  return state.profile.chart?.placements || state.profile.chartPlacements || defaultNatalPlacements;
}

function getNatalAspects() {
  return state.profile.chart?.aspects || state.profile.chartAspects || defaultNatalAspects;
}

function renderPlacements() {
  const list = document.querySelector("[data-placement-list]");
  if (!list) return;

  const placements = getNatalPlacements();
  const count = document.querySelector("[data-placement-count]");
  if (count) count.textContent = String(placements.length);

  list.textContent = "";
  placements.forEach((placement) => {
    const row = document.createElement("article");
    row.className = "placement-row";

    const glyph = document.createElement("span");
    const glyphText = placement.glyph || placement.body?.slice(0, 2) || "✦";
    const planetClass = getPlacementClass(placement.body || placement.planet || glyphText);
    glyph.className = "placement-glyph";
    glyph.classList.add(planetClass);
    const icon = getPlacementIcon(planetClass);

    if (icon) {
      glyph.classList.add("svg-glyph");
      glyph.innerHTML = icon;
    } else {
      glyph.classList.toggle("text-glyph", glyphText.length > 1);
      glyph.textContent = glyphText;
    }

    const body = document.createElement("div");
    body.className = "placement-body";

    const name = document.createElement("strong");
    name.textContent = placement.body || placement.planet || "Placement";

    const detail = document.createElement("small");
    detail.textContent = `${placement.sign || "Sign"} · ${placement.house || "House"} house`;

    body.append(name, detail);

    const degree = document.createElement("span");
    degree.className = "placement-degree";
    degree.textContent = placement.degree || "0°00′";

    row.append(glyph, body, degree);
    list.appendChild(row);
  });
}

function getPlacementClass(name) {
  return `placement-${String(name || "planet").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "planet"}`;
}

function getPlacementIcon(planetClass) {
  const svgAttrs = "viewBox=\"0 0 64 64\" aria-hidden=\"true\" focusable=\"false\"";
  const lineAttrs = "fill=\"none\" stroke=\"currentColor\" stroke-width=\"4\" stroke-linecap=\"round\" stroke-linejoin=\"round\"";
  const icons = {
    "placement-sun": `<svg ${svgAttrs}><circle ${lineAttrs} cx="32" cy="32" r="15"/><circle cx="32" cy="32" r="4.2" fill="currentColor"/></svg>`,
    "placement-moon": `<svg ${svgAttrs}><path ${lineAttrs} d="M42 9c-10 3-18 12.5-18 23s8 20 18 23C26 55 13 45 13 32S26 9 42 9Z"/></svg>`,
    "placement-mercury": `<svg ${svgAttrs}><path ${lineAttrs} d="M23 12c2.4 5.3 5.4 8 9 8s6.6-2.7 9-8"/><circle ${lineAttrs} cx="32" cy="30" r="10"/><path ${lineAttrs} d="M32 40v13M24 47h16"/></svg>`,
    "placement-venus": `<svg ${svgAttrs}><circle ${lineAttrs} cx="32" cy="25" r="11"/><path ${lineAttrs} d="M32 36v16M24 44h16"/></svg>`,
    "placement-mars": `<svg ${svgAttrs}><circle ${lineAttrs} cx="25" cy="39" r="11"/><path ${lineAttrs} d="M33 31 49 15M39 15h10v10"/></svg>`,
    "placement-jupiter": `<svg ${svgAttrs}><path ${lineAttrs} d="M20 19c14-1 18 15 3 22M15 41h31M36 14v38"/></svg>`,
    "placement-saturn": `<svg ${svgAttrs}><path ${lineAttrs} d="M24 15v35M17 25h18M24 36c13-3 22 6 9 16"/></svg>`,
    "placement-uranus": `<svg ${svgAttrs}><path ${lineAttrs} d="M19 16v25M45 16v25M19 29h26M32 12v33"/><circle ${lineAttrs} cx="32" cy="50" r="5"/></svg>`,
    "placement-neptune": `<svg ${svgAttrs}><path ${lineAttrs} d="M32 15v36M20 18c0 11 5 17 12 17s12-6 12-17M24 45h16"/></svg>`,
    "placement-pluto": `<svg ${svgAttrs}><path ${lineAttrs} d="M23 51V15h12c7 0 12 4.4 12 10.5S42 36 35 36H23M23 51h25"/></svg>`,
    "placement-north-node": `<svg ${svgAttrs}><path ${lineAttrs} d="M17 42c0-11 6.5-19 15-19s15 8 15 19"/><circle ${lineAttrs} cx="19" cy="44" r="5"/><circle ${lineAttrs} cx="45" cy="44" r="5"/></svg>`,
    "placement-chiron": `<svg ${svgAttrs}><path ${lineAttrs} d="M32 13v29M32 24l12-11M32 24l12 11"/><circle ${lineAttrs} cx="32" cy="49" r="7"/></svg>`
  };

  return icons[planetClass] || "";
}

function renderAspects() {
  const list = document.querySelector("[data-aspect-list]");
  if (!list) return;

  const aspects = getNatalAspects();
  const count = document.querySelector("[data-aspect-count]");
  if (count) count.textContent = String(aspects.length);

  list.textContent = "";
  aspects.forEach((aspect) => {
    const row = document.createElement("article");
    row.className = "aspect-row";

    const title = document.createElement("strong");
    title.textContent = `${aspect.first} ${aspect.aspect} ${aspect.second}`;

    const orb = document.createElement("span");
    orb.textContent = aspect.orb ? `Orb ${aspect.orb}` : "Major aspect";

    row.append(title, orb);
    list.appendChild(row);
  });
}

function renderChartBalance() {
  const grid = document.querySelector("[data-chart-balance]");
  if (!grid) return;

  const balance = state.profile.chart?.balance || state.profile.chartBalance || defaultChartBalance;
  const items = [
    ["Elements", balance.dominantElement || "Balanced", balance.elements || defaultChartBalance.elements],
    ["Modality", balance.dominantModality || "Balanced", balance.modality || defaultChartBalance.modality],
    ["Sect", getChartSect(), balance.sectNote || defaultChartBalance.sectNote]
  ];

  grid.textContent = "";
  items.forEach(([label, title, value]) => {
    const card = document.createElement("article");
    card.className = "balance-card";

    const labelEl = document.createElement("span");
    labelEl.textContent = label;

    const titleEl = document.createElement("strong");
    titleEl.textContent = title;

    const valueEl = document.createElement("p");
    valueEl.textContent = value;

    card.append(labelEl, titleEl, valueEl);
    grid.appendChild(card);
  });
}

function getSavedPeopleCharts() {
  if (!Array.isArray(state.profile.savedPeopleCharts)) {
    state.profile.savedPeopleCharts = [];
  }

  return state.profile.savedPeopleCharts;
}

function renderSavedPeople() {
  const list = document.querySelector("[data-saved-people-list]");
  if (!list) return;

  const savedPeople = getSavedPeopleCharts();
  list.textContent = "";

  if (!savedPeople.length) {
    const empty = document.createElement("article");
    empty.className = "saved-person-card empty";
    const title = document.createElement("strong");
    title.textContent = "No saved people yet";
    const copy = document.createElement("p");
    copy.textContent = "Add a person above to keep their birth details ready for relationship, family, or client readings.";
    empty.append(title, copy);
    list.appendChild(empty);
    return;
  }

  savedPeople.forEach((person) => {
    const card = document.createElement("article");
    card.className = "saved-person-card";

    const meta = document.createElement("span");
    meta.textContent = person.connection || "Saved chart";

    const title = document.createElement("strong");
    title.textContent = person.name || "Unnamed person";

    const details = document.createElement("p");
    details.textContent = [
      person.birthDate,
      person.birthTime || "Time unknown",
      [person.birthCity, person.birthCountry].filter(Boolean).join(", ")
    ].filter(Boolean).join(" · ");

    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "saved-person-remove";
    remove.dataset.removePerson = person.id;
    remove.textContent = "Remove";

    card.append(meta, title, details, remove);
    list.appendChild(card);
  });
}

function renderJournal() {
  renderJournalSky();
  renderJournalEntries();
}

function renderJournalSky() {
  const moonPhase = getMoonPhaseInfo(new Date());
  const transit = getSignificantTransitPreview(new Date());
  const moonTitle = document.querySelector("[data-journal-moon-phase]");
  const moonCopy = document.querySelector("[data-journal-moon-copy]");
  const transitTitle = document.querySelector("[data-journal-transit-title]");
  const transitCopy = document.querySelector("[data-journal-transit-copy]");

  if (moonTitle) moonTitle.textContent = moonPhase.name;
  if (moonCopy) moonCopy.textContent = `${moonPhase.illumination}% illuminated · ${moonPhase.copy}`;
  if (transitTitle) transitTitle.textContent = transit.title;
  if (transitCopy) transitCopy.textContent = transit.copy;
}

function getMoonPhaseInfo(date) {
  const synodicMonth = 29.53058867;
  const knownNewMoon = Date.UTC(2000, 0, 6, 18, 14);
  const daysSince = (date.getTime() - knownNewMoon) / 86400000;
  const age = ((daysSince % synodicMonth) + synodicMonth) % synodicMonth;
  const illumination = Math.round(((1 - Math.cos((2 * Math.PI * age) / synodicMonth)) / 2) * 100);
  const phases = [
    [1.84566, "New Moon", "Set the seed and listen before moving."],
    [5.53699, "Waxing Crescent", "Protect the intention while it gathers strength."],
    [9.22831, "First Quarter", "Choose the action that proves the intention is real."],
    [12.91963, "Waxing Gibbous", "Refine the plan and notice what wants devotion."],
    [16.61096, "Full Moon", "Name what is visible, heightened, or ready to release."],
    [20.30228, "Waning Gibbous", "Integrate the lesson and share what became clear."],
    [23.99361, "Last Quarter", "Edit, simplify, and choose what no longer comes with you."],
    [27.68493, "Waning Crescent", "Rest, close the loop, and prepare for renewal."],
    [synodicMonth, "New Moon", "Set the seed and listen before moving."]
  ];
  const phase = phases.find(([limit]) => age < limit) || phases[0];

  return {
    name: phase[1],
    copy: phase[2],
    illumination
  };
}

function getSignificantTransitPreview(date) {
  const transitFocus = [
    {
      title: "Moon emotional weather",
      copy: "Track the feeling before the story. Your body may reveal the timing first."
    },
    {
      title: "Mercury message window",
      copy: "Notice repeated words, decisions, emails, and conversations asking for clarity."
    },
    {
      title: "Venus value check",
      copy: "Journal where love, beauty, money, and self-worth are asking for gentler alignment."
    },
    {
      title: "Mars action signal",
      copy: "Name the boundary, desire, or brave move that wants a cleaner channel."
    },
    {
      title: "Jupiter growth opening",
      copy: "Look for the door that expands your faith without scattering your focus."
    },
    {
      title: "Saturn mastery lesson",
      copy: "Write down the structure, commitment, or limit that is actually protecting your future."
    },
    {
      title: "Pluto release pattern",
      copy: "Notice what feels intense, magnetic, or ready to transform instead of repeat."
    }
  ];
  const startOfYear = new Date(date.getFullYear(), 0, 0);
  const dayOfYear = Math.floor((date - startOfYear) / 86400000);

  return transitFocus[dayOfYear % transitFocus.length];
}

function getJournalEntries() {
  if (!Array.isArray(state.profile.journalEntries)) {
    state.profile.journalEntries = [];
  }

  return state.profile.journalEntries;
}

function saveJournalEntry(formElement) {
  const form = new FormData(formElement);
  const title = String(form.get("journalTitle") || "").trim();
  const body = String(form.get("journalBody") || "").trim();
  if (!title || !body) return;

  const moonPhase = getMoonPhaseInfo(new Date());
  const transit = getSignificantTransitPreview(new Date());
  getJournalEntries().unshift({
    id: `journal-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    title,
    body,
    moonPhase: moonPhase.name,
    transit: transit.title,
    savedAt: new Date().toISOString()
  });

  saveState();
  formElement.reset();
  renderJournalEntries();
  showSaveToast("Journal entry saved.");
}

function renderJournalEntries() {
  const list = document.querySelector("[data-journal-entry-list]");
  if (!list) return;

  const entries = getJournalEntries();
  list.textContent = "";

  if (!entries.length) {
    const empty = document.createElement("article");
    empty.className = "journal-saved-entry empty";
    const title = document.createElement("strong");
    title.textContent = "No journal entries yet";
    const copy = document.createElement("p");
    copy.textContent = "Save your first moon note to begin building a private pattern archive.";
    empty.append(title, copy);
    list.appendChild(empty);
    return;
  }

  entries.forEach((entry) => {
    const card = document.createElement("article");
    card.className = "journal-saved-entry";

    const meta = document.createElement("span");
    meta.textContent = `${formatReadingDate(entry.savedAt)} · ${entry.moonPhase} · ${entry.transit}`;

    const title = document.createElement("strong");
    title.textContent = entry.title;

    const body = document.createElement("p");
    body.textContent = truncateText(entry.body, 140);

    card.append(meta, title, body);
    list.appendChild(card);
  });
}

function openPersonChartDialog() {
  if (!personChartDialog) return;

  if (typeof personChartDialog.showModal === "function") {
    personChartDialog.showModal();
  } else {
    personChartDialog.setAttribute("open", "");
  }

  resetPersonChartDialogScroll();
}

function closePersonChartDialog() {
  if (!personChartDialog) return;
  if (typeof personChartDialog.close === "function") personChartDialog.close();
  else personChartDialog.removeAttribute("open");
}

function resetPersonChartDialogScroll() {
  const inner = personChartDialog?.querySelector(".person-chart-dialog-inner");
  const firstField = personChartDialog?.querySelector("input");

  const reset = () => {
    personChartDialog.scrollTop = 0;
    inner?.scrollTo?.({ top: 0, left: 0, behavior: "auto" });
    if (inner) inner.scrollTop = 0;
  };

  reset();
  requestAnimationFrame(() => {
    reset();
    firstField?.focus?.({ preventScroll: true });
  });
  window.setTimeout(reset, 80);
}

function updateAskWelcome() {
  const welcomeCopy = document.querySelector("[data-oracle-welcome-copy]");
  const defaultChoices = document.querySelector("[data-default-ask-choices]");
  const loveChoices = document.querySelector("[data-love-choices]");
  const moneyChoices = document.querySelector("[data-money-choices]");
  const timingChoices = document.querySelector("[data-timing-choices]");
  const karmaChoices = document.querySelector("[data-karma-choices]");
  const askScreen = document.querySelector("#ask");
  if (!welcomeCopy || !defaultChoices || !loveChoices || !moneyChoices || !timingChoices || !karmaChoices) return;

  const name = getOracleClientName();
  const namePart = name ? `, ${name}` : "";
  const isLoveMode = state.chatMode === "love";
  const isMoneyMode = state.chatMode === "money";
  const isTimingMode = state.chatMode === "timing";
  const isKarmaMode = state.chatMode === "karma";
  const isGuidedMode = isLoveMode || isMoneyMode || isTimingMode || isKarmaMode;

  askScreen?.classList.toggle("love-chat-active", isGuidedMode);
  defaultChoices.hidden = isGuidedMode;

  if (isGuidedMode) {
    welcomeCopy.textContent = `I’m here for you${namePart}. Do you have a question in mind, or do you want me to do any of the following?`;
    loveChoices.hidden = !isLoveMode;
    moneyChoices.hidden = !isMoneyMode;
    timingChoices.hidden = !isTimingMode;
    karmaChoices.hidden = !isKarmaMode;
    return;
  }

  welcomeCopy.textContent = `I’m here for you${namePart}. Ask about love, money, timing, purpose, healing, or the next decision in front of you.`;
  loveChoices.hidden = true;
  moneyChoices.hidden = true;
  timingChoices.hidden = true;
  karmaChoices.hidden = true;
}

function getOracleClientName() {
  const savedName = state.profile.name || state.profile.firstName || state.profile.displayName;
  if (savedName) return String(savedName).trim().split(/\s+/)[0];

  const email = state.profile.email;
  if (!email || typeof email !== "string") return "";

  const localPart = email.split("@")[0]?.replace(/[._-]+/g, " ").trim();
  if (!localPart) return "";

  return localPart.charAt(0).toUpperCase() + localPart.slice(1);
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

function openLessonDialog(level) {
  const content = lessonLevels[level];
  if (!lessonDialog || !content) return;

  activeLessonLevel = level;
  lessonDialog.querySelector("[data-lesson-dialog-level]").textContent = content.label;
  lessonDialog.querySelector("[data-lesson-dialog-title]").textContent = content.title;
  lessonDialog.querySelector("[data-lesson-dialog-body]").textContent = content.body;

  if (typeof lessonDialog.showModal === "function") {
    lessonDialog.showModal();
  } else {
    lessonDialog.setAttribute("open", "");
  }
}

function closeLessonDialog() {
  activeLessonLevel = "";
  if (!lessonDialog) return;
  if (typeof lessonDialog.close === "function") lessonDialog.close();
  else lessonDialog.removeAttribute("open");
}

function beginLesson() {
  const content = lessonLevels[activeLessonLevel];
  closeLessonDialog();
  if (content) showSaveToast(`${content.label} lesson begins.`);
}

function getAccessPillState() {
  const isOwner = oracleOwnerEmails.has(
    String(state.profile.email || "").trim().toLowerCase()
  );
  const accessEndRaw = state.profile.access_end || state.profile.accessEnd;
  const accessEnd = parseAccessEndDate(accessEndRaw);
  const hasValidEnd = accessEnd && !Number.isNaN(accessEnd.valueOf());
  const isFuture = hasValidEnd && accessEnd > new Date();
  const accessStatus = String(
    state.profile.access_status || state.profile.payment_status || ""
  ).trim().toUpperCase();
  const hasAuthenticatedAccess = Boolean(
    state.profile.access_code
    || state.profile.accessCode
    || state.profile.permission_level
    || state.profile.reading_type
    || accessStatus
  );
  const statusAllowsAccess = !accessStatus
    || ["ACTIVE", "VALID", "PAID", "TRIALING", "DEMO"].includes(accessStatus);
  const configuredPlanId = state.profile.plan_id || state.profile.plan;
  const configuredPlan = pricingConfig?.getPlan(configuredPlanId);
  const configuredAccountState = configuredPlan
    ? pricingConfig.evaluateAccountState({
        plan_id: configuredPlanId,
        payment_status: state.profile.payment_status || state.profile.paymentStatus,
        access_end: accessEndRaw
      })
    : null;

  const active = isOwner || (configuredAccountState
    ? configuredAccountState.active
    : accessEndRaw
      ? Boolean(isFuture && statusAllowsAccess)
      : hasAuthenticatedAccess
        ? false
        : true);

  return active
    ? { active: true, icon: "✓", text: "Oracle Access Active" }
    : { active: false, icon: "×", text: "Oracle Access Inactive" };
}

function getAccessDisplay() {
  const accessEndRaw = state.profile.access_end || state.profile.accessEnd;
  const accessEnd = parseAccessEndDate(accessEndRaw);
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

function setCheckoutStatus(message, type = "") {
  if (!checkoutStatus) return;

  checkoutStatus.textContent = message;
  checkoutStatus.classList.toggle("error", type === "error");
  checkoutStatus.classList.toggle("ready", type === "ready");
}

function setCheckoutButtonLoading(button, isLoading) {
  if (!button) return;

  if (!button.dataset.originalText) {
    button.dataset.originalText = button.textContent;
  }

  button.disabled = isLoading;
  button.textContent = isLoading ? "Preparing Checkout..." : button.dataset.originalText;
}

function getCheckoutEmail() {
  return String(checkoutEmailInput?.value || state.profile.email || "").trim();
}

function checkoutReturnUrl(routeName) {
  return `${window.location.origin}${window.location.pathname}${window.location.search}#${routeName}`;
}

async function startPlanCheckout(planId, button) {
  const plan = pricingConfig?.getPlan(planId);
  if (!plan) {
    setCheckoutStatus("Please choose a valid Oracle plan.", "error");
    return;
  }

  const email = getCheckoutEmail();
  if (!email) {
    setCheckoutStatus("Enter your email first so your account can be matched after checkout.", "error");
    checkoutEmailInput?.focus();
    return;
  }

  state.profile.email = email;
  saveState();
  updateProfile();
  setCheckoutStatus(`Preparing ${plan.plan_name} checkout...`, "ready");
  setCheckoutButtonLoading(button, true);

  try {
    const response = await fetch(checkoutEndpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        plan_id: planId,
        email,
        customer_name: state.profile.name || "",
        return_url: checkoutReturnUrl("activate"),
        cancel_url: checkoutReturnUrl("pricing")
      })
    });
    const data = await response.json().catch(() => ({}));

    if (!response.ok || !data.success) {
      setCheckoutStatus(data.message || "Checkout is not available yet.", "error");
      return;
    }

    if (!data.checkout_url) {
      setCheckoutStatus("Checkout did not return a payment link yet.", "error");
      return;
    }

    setCheckoutStatus("Opening secure checkout...", "ready");
    window.location.assign(data.checkout_url);
  } catch {
    setCheckoutStatus("Checkout could not connect yet. Check the backend webhook setup.", "error");
  } finally {
    setCheckoutButtonLoading(button, false);
  }
}

function setSignInStatus(message, type = "") {
  if (!signInStatus) return;

  signInStatus.textContent = message;
  signInStatus.hidden = !message;
  signInStatus.classList.toggle("error", type === "error");
  signInStatus.classList.toggle("ready", type === "ready");
}

function setAccessCodeStatus(message, type = "") {
  if (!accessCodeStatus) return;

  accessCodeStatus.textContent = message;
  accessCodeStatus.hidden = !message;
  accessCodeStatus.classList.toggle("error", type === "error");
  accessCodeStatus.classList.toggle("ready", type === "ready");
}

function setEmailSignInStatus(message, type = "") {
  if (!emailSignInStatus) return;

  emailSignInStatus.textContent = message;
  emailSignInStatus.hidden = !message;
  emailSignInStatus.classList.toggle("error", type === "error");
  emailSignInStatus.classList.toggle("ready", type === "ready");
}

function openAccessCodeDialog() {
  if (!accessCodeDialog) return;
  setAccessCodeStatus("");

  if (typeof accessCodeDialog.showModal === "function") {
    accessCodeDialog.showModal();
  } else {
    accessCodeDialog.setAttribute("open", "");
  }

  window.requestAnimationFrame(() => {
    accessCodeForm?.elements?.accessCode?.focus();
  });
}

function closeAccessCodeDialog() {
  if (!accessCodeDialog) return;
  if (typeof accessCodeDialog.close === "function") accessCodeDialog.close();
  else accessCodeDialog.removeAttribute("open");
}

async function authenticateAccessCode(accessCode) {
  const submitButton = accessCodeForm?.querySelector('[type="submit"]');
  if (submitButton) {
    submitButton.disabled = true;
    submitButton.textContent = "Checking Access...";
  }
  setAccessCodeStatus("Checking your Oracle access...", "ready");

  try {
    const response = await fetch(accessCodeAuthEndpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ access_code: accessCode })
    });
    const data = await response.json().catch(() => ({}));

    if (!response.ok || !data.valid) {
      setAccessCodeStatus(
        data.message || "This code could not be activated.",
        "error"
      );
      return;
    }

    state.profile.access_code = accessCode;
    state.profile.access_status = data.status || "ACTIVE";
    state.profile.payment_status = data.status || state.profile.payment_status || "ACTIVE";
    saveAuthenticatedProfile(data);
    setAccessCodeStatus("Access confirmed. Opening your private space...", "ready");

    window.setTimeout(() => {
      closeAccessCodeDialog();
      go("birth");
    }, 420);
  } catch {
    setAccessCodeStatus("The Oracle could not check this code yet. Please try again.", "error");
  } finally {
    if (submitButton) {
      submitButton.disabled = false;
      submitButton.textContent = "Activate My Oracle";
    }
  }
}

async function authenticateEmail(email, formElement) {
  const submitButton = formElement?.querySelector('[type="submit"]');
  if (submitButton) {
    submitButton.disabled = true;
    submitButton.textContent = "Checking Access...";
  }
  setEmailSignInStatus("Checking your Oracle access...", "ready");

  try {
    const response = await fetch(emailAuthEndpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email })
    });
    const data = await response.json().catch(() => ({}));

    if (!response.ok || !data.success) {
      setEmailSignInStatus(
        data.message || "No active Oracle access was found for this email.",
        "error"
      );
      return;
    }

    saveAuthenticatedProfile(data);
    setEmailSignInStatus("Access confirmed. Opening your private space...", "ready");
    window.setTimeout(() => go("birth"), 420);
  } catch {
    setEmailSignInStatus("Oracle access could not be checked yet. Please try again.", "error");
  } finally {
    if (submitButton) {
      submitButton.disabled = false;
      submitButton.textContent = "Continue with Email";
    }
  }
}

function loadGoogleIdentityScript() {
  if (globalThis.google?.accounts?.id) return Promise.resolve();
  if (googleIdentityScriptPromise) return googleIdentityScriptPromise;

  googleIdentityScriptPromise = new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = "https://accounts.google.com/gsi/client";
    script.async = true;
    script.defer = true;
    script.dataset.googleIdentityScript = "true";
    script.addEventListener("load", () => resolve());
    script.addEventListener("error", () => reject(new Error("Google sign-in script could not load.")));
    document.head.append(script);
  });

  return googleIdentityScriptPromise;
}

function saveAuthenticatedProfile(data) {
  const hasPermissionLevel = Object.prototype.hasOwnProperty.call(data, "permission_level");
  const hasReadingType = Object.prototype.hasOwnProperty.call(data, "reading_type");
  const hasExpirationDate = Object.prototype.hasOwnProperty.call(data, "expiration_date");
  const hasSheetAccessFields = hasPermissionLevel || hasReadingType || hasExpirationDate;

  state.profile.email = data.email || state.profile.email || "";
  state.profile.customer_name = data.customer_name || state.profile.customer_name || "";
  if (hasExpirationDate) {
    state.profile.access_end = data.expiration_date || "";
  }
  if (hasPermissionLevel) {
    state.profile.permission_level = data.permission_level || "";
  }
  if (hasReadingType) {
    state.profile.reading_type = data.reading_type || "";
  }
  if (Object.prototype.hasOwnProperty.call(data, "status")) {
    state.profile.access_status = data.status || "";
  }
  state.profile.google_picture = data.picture || state.profile.google_picture || "";
  if (Object.prototype.hasOwnProperty.call(data, "plan_id")) {
    state.profile.plan_id = data.plan_id || "";
  } else if (hasSheetAccessFields) {
    state.profile.plan_id = "";
    state.profile.plan = "";
  }
  state.profile.payment_status = data.payment_status
    || data.status
    || state.profile.payment_status
    || "";

  const authenticatedAllAccess = typeof data.all_access === "boolean"
    ? data.all_access
    : data.all_in_access;
  if (typeof authenticatedAllAccess === "boolean") {
    state.profile.all_in_access = authenticatedAllAccess;
  } else if (hasPermissionLevel || hasReadingType) {
    const accessMarkers = [
      data.permission_level,
      data.reading_type
    ].filter(Boolean).join(" ").replace(/[_-]+/g, " ").toUpperCase();
    state.profile.all_in_access = /\b(ALL\s*ACCESS|FULL(?:\s*ACCESS)?|VIP|FOUNDER|INNER\s*CIRCLE|UNLIMITED)\b/.test(
      accessMarkers
    );
  }

  if (!state.profile.name && data.customer_name) {
    state.profile.name = data.customer_name;
  }

  saveState();
  updateProfile();
}

async function authenticateGoogleCredential(credential) {
  setSignInStatus("Checking your Oracle account...", "ready");

  try {
    const response = await fetch(googleAuthEndpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ credential })
    });
    const data = await response.json().catch(() => ({}));

    if (!response.ok || !data.success) {
      const message = data.message || "Google sign-in could not open this account yet.";
      setSignInStatus(message, "error");
      if (data.status === "ACCOUNT_NOT_FOUND" || data.status === "INACTIVE" || data.status === "EXPIRED") {
        setTimeout(() => go("pricing"), 1100);
      }
      return;
    }

    saveAuthenticatedProfile(data);
    setSignInStatus("Signed in. Opening your Oracle...", "ready");
    setTimeout(() => go("birth"), 420);
  } catch {
    setSignInStatus("Google sign-in could not connect to the backend yet.", "error");
  }
}

function handleGoogleCredential(response) {
  const credential = response?.credential;
  if (!credential) {
    setSignInStatus("Google sign-in did not return a credential.", "error");
    return;
  }

  authenticateGoogleCredential(credential);
}

async function initializeGoogleSignIn() {
  if (!googleButtonHost && !googleSignInFallback) return;

  setSignInStatus("Loading Google sign-in...", "ready");

  try {
    const response = await fetch(googleAuthConfigEndpoint);
    const config = await response.json().catch(() => ({}));
    const clientId = config.client_id || globalThis.ASTROMEG_GOOGLE_CLIENT_ID || "";

    if (!response.ok || !clientId) {
      throw new Error(config.message || "Google sign-in needs GOOGLE_CLIENT_ID in Render.");
    }

    await loadGoogleIdentityScript();

    globalThis.google.accounts.id.initialize({
      client_id: clientId,
      callback: handleGoogleCredential,
      auto_select: false,
      cancel_on_tap_outside: true
    });

    if (googleButtonHost) {
      googleButtonHost.innerHTML = "";
      globalThis.google.accounts.id.renderButton(googleButtonHost, {
        theme: "outline",
        size: "large",
        shape: "pill",
        text: "continue_with",
        width: 300
      });
    }

    if (googleSignInFallback) googleSignInFallback.hidden = true;
    setSignInStatus("", "");
  } catch (error) {
    if (googleSignInFallback) googleSignInFallback.hidden = false;
    setSignInStatus(error.message || "Google sign-in needs setup in Render.", "error");
  }
}

function setZodiacPlaylist(signOrIndex) {
  const nextIndex = typeof signOrIndex === "number"
    ? signOrIndex
    : zodiacPlaylists.findIndex((playlist) => playlist.id === signOrIndex);

  if (nextIndex < 0) return;

  activeZodiacIndex = (nextIndex + zodiacPlaylists.length) % zodiacPlaylists.length;
  const playlist = zodiacPlaylists[activeZodiacIndex];

  document.querySelectorAll("[data-playlist-sign]").forEach((button) => {
    const isActive = button.dataset.playlistSign === playlist.id;
    button.classList.toggle("active", isActive);
    button.setAttribute("aria-pressed", String(isActive));

    if (button.classList.contains("zodiac-playlist-card")) {
      button.hidden = !isActive;
      button.tabIndex = isActive ? 0 : -1;
      button.setAttribute("aria-label", `Open ${playlist.name} playlist`);
    }
  });

  const heroImage = document.querySelector("[data-zodiac-hero-image]");
  const glyph = document.querySelector("[data-zodiac-glyph]");
  const meta = document.querySelector("[data-zodiac-meta]");
  const name = document.querySelector("[data-zodiac-name]");
  const theme = document.querySelector("[data-zodiac-theme]");
  const toneOne = document.querySelector("[data-zodiac-tone-one]");
  const toneTwo = document.querySelector("[data-zodiac-tone-two]");
  const toneThree = document.querySelector("[data-zodiac-tone-three]");
  const note = document.querySelector("[data-zodiac-note]");
  const listenLink = document.querySelector("[data-playlist-listen]");
  const embedFrame = document.querySelector("[data-playlist-embed]");

  if (heroImage) {
    heroImage.src = playlist.image;
    heroImage.alt = `${playlist.name} zodiac playlist artwork`;
  }

  if (glyph) glyph.textContent = playlist.glyph;
  if (meta) meta.textContent = playlist.meta;
  if (name) name.textContent = playlist.name;
  if (theme) theme.textContent = playlist.theme;
  if (toneOne) toneOne.textContent = playlist.tones[0];
  if (toneTwo) toneTwo.textContent = playlist.tones[1];
  if (toneThree) toneThree.textContent = playlist.tones[2];
  if (note) note.textContent = playlist.note;

  if (listenLink) {
    listenLink.href = playlist.url;
    listenLink.setAttribute("aria-label", `Listen to the ${playlist.name} playlist on SoundCloud`);
  }

  if (embedFrame) {
    embedFrame.src = getSoundCloudEmbedUrl(playlist.url);
    embedFrame.title = `${playlist.name} SoundCloud playlist`;
  }
}

function shiftZodiacPlaylist(direction) {
  setZodiacPlaylist(activeZodiacIndex + direction);
}

function setMeditationPlaylist(choiceOrIndex) {
  const nextIndex = typeof choiceOrIndex === "number"
    ? choiceOrIndex
    : meditationPlaylists.findIndex((playlist) => playlist.id === choiceOrIndex);

  if (nextIndex < 0) return;

  activeMeditationIndex = (nextIndex + meditationPlaylists.length) % meditationPlaylists.length;
  const playlist = meditationPlaylists[activeMeditationIndex];

  document.querySelectorAll("[data-meditation-choice]").forEach((button) => {
    const isActive = button.dataset.meditationChoice === playlist.id;
    button.classList.toggle("active", isActive);
    button.setAttribute("aria-pressed", String(isActive));
  });

  const copy = document.querySelector("[data-meditation-copy]");
  const brand = document.querySelector(".meditation-player-brand");
  const brandTitle = document.querySelector("[data-meditation-brand-title]");
  const brandVideo = document.querySelector("[data-meditation-brand-video]");
  const brandVideoSource = document.querySelector("[data-meditation-brand-video-source]");
  const embedFrame = document.querySelector("[data-meditation-embed]");

  if (copy) copy.textContent = playlist.copy;
  if (brandTitle) brandTitle.textContent = `Guided Meditation: ${playlist.name}`;

  if (brand && brandVideo && brandVideoSource) {
    if (playlist.banner) {
      if (brandVideoSource.getAttribute("src") !== playlist.banner) {
        brandVideoSource.setAttribute("src", playlist.banner);
        brandVideo.load();
      }
      brand.classList.add("has-video");
      brandVideo.hidden = false;
    } else {
      brand.classList.remove("has-video");
      brandVideo.hidden = true;
      brandVideoSource.removeAttribute("src");
      brandVideo.load();
    }
  }

  if (embedFrame) {
    embedFrame.src = getSoundCloudPlaylistEmbedUrl(playlist.url);
    embedFrame.title = "Astromeg Oracle guided meditation playlist";
  }

  return playlist;
}

function openMeditationPage(choiceId, push = true) {
  const playlist = setMeditationPlaylist(choiceId);
  if (!playlist) return;
  go("guided-meditation", push, `meditation-${playlist.id}`);
}

function getSoundCloudEmbedUrl(url) {
  const params = new URLSearchParams({
    url,
    color: "#9b6ed6",
    auto_play: "false",
    hide_related: "true",
    show_comments: "false",
    show_user: "true",
    show_reposts: "false",
    show_teaser: "false",
    visual: "true"
  });

  return `https://w.soundcloud.com/player/?${params.toString()}`;
}

function getSoundCloudPlaylistEmbedUrl(url) {
  const params = new URLSearchParams({
    url,
    color: "#9b6ed6",
    auto_play: "false",
    hide_related: "true",
    show_comments: "false",
    show_user: "true",
    show_reposts: "false",
    show_teaser: "false",
    show_artwork: "true",
    visual: "false"
  });

  return `https://w.soundcloud.com/player/?${params.toString()}`;
}

function openZodiacPlaylistLink() {
  const playlist = zodiacPlaylists[activeZodiacIndex];
  if (!playlist?.url) return;

  const opened = window.open(playlist.url, "_blank", "noopener,noreferrer");
  if (!opened) {
    window.location.assign(playlist.url);
  }
}

function getSavedReadings() {
  if (!Array.isArray(state.profile.savedReadings)) {
    state.profile.savedReadings = [];
  }

  return state.profile.savedReadings;
}

function getReadingCategoryNames() {
  const names = defaultReadingCategories.map((category) => category.name);

  getSavedReadings().forEach((reading) => {
    const category = normalizeCategoryName(reading.category);
    if (category && !names.includes(category)) names.push(category);
  });

  return names;
}

function normalizeCategoryName(value) {
  return String(value || "").replace(/\s+/g, " ").trim();
}

function inferReadingCategory(question) {
  const text = String(question || "").toLowerCase();

  if (state.chatMode === "love" || /(love|relationship|partner|wife|husband|attraction|person|heart)/.test(text)) {
    return "Relationship Pattern";
  }

  if (state.chatMode === "money" || /(money|career|wealth|income|business|client|success|visibility|goal)/.test(text)) {
    return "Year-Ahead Alignment";
  }

  if (state.chatMode === "timing" || /(timing|window|transit|date|launch|pause|prepare|moon|sky|when|timeline|predictive|age)/.test(text)) {
    return "Timing Window";
  }

  if (state.chatMode === "karma" || /(karma|karmic|saturn|lesson|master|inner child|wounding|healing|soul)/.test(text)) {
    return "Karma & Healing";
  }

  return "Relationship Pattern";
}

function createReadingDraft(question, answer) {
  const id = `reading-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  const draft = {
    id,
    question,
    answer,
    category: inferReadingCategory(question),
    createdAt: new Date().toISOString()
  };

  readingDrafts.set(id, draft);
  return draft;
}

function populateSaveCategoryOptions(selectedCategory) {
  if (!saveReadingCategory) return;

  saveReadingCategory.textContent = "";
  getReadingCategoryNames().forEach((category) => {
    const option = document.createElement("option");
    option.value = category;
    option.textContent = category;
    saveReadingCategory.appendChild(option);
  });

  const customOption = document.createElement("option");
  customOption.value = customCategoryValue;
  customOption.textContent = "Create a new category";
  saveReadingCategory.appendChild(customOption);

  saveReadingCategory.value = getReadingCategoryNames().includes(selectedCategory)
    ? selectedCategory
    : defaultReadingCategories[0].name;
  updateCustomCategoryField();
}

function openSaveReadingDialog(draftId) {
  const draft = readingDrafts.get(draftId);
  if (!draft || !saveReadingDialog) return;

  activeReadingDraft = draft;
  populateSaveCategoryOptions(draft.category);

  if (saveReadingPreview) {
    saveReadingPreview.textContent = `Suggested category: ${draft.category}. "${truncateText(draft.question, 92)}"`;
  }

  if (customCategoryInput) customCategoryInput.value = "";

  if (typeof saveReadingDialog.showModal === "function") {
    saveReadingDialog.showModal();
  } else {
    saveReadingDialog.setAttribute("open", "");
  }
}

function closeSaveReadingDialog() {
  activeReadingDraft = null;
  if (saveReadingDialog?.open) saveReadingDialog.close();
  saveReadingDialog?.removeAttribute("open");
}

function updateCustomCategoryField() {
  const isCustom = saveReadingCategory?.value === customCategoryValue;
  if (customCategoryWrap) customCategoryWrap.hidden = !isCustom;

  if (customCategoryInput) {
    customCategoryInput.required = Boolean(isCustom);
    customCategoryInput.setCustomValidity("");
    if (isCustom) customCategoryInput.focus({ preventScroll: true });
  }
}

function saveActiveReading() {
  if (!activeReadingDraft || !saveReadingForm) return;

  const form = new FormData(saveReadingForm);
  const selectedCategory = normalizeCategoryName(form.get("category"));
  const customCategory = normalizeCategoryName(form.get("customCategory"));
  const category = selectedCategory === customCategoryValue ? customCategory : selectedCategory;

  if (!category) {
    customCategoryInput?.setCustomValidity("Name this category to save your reading.");
    customCategoryInput?.reportValidity();
    return;
  }

  customCategoryInput?.setCustomValidity("");

  const savedReading = {
    id: activeReadingDraft.id,
    category,
    title: createReadingTitle(activeReadingDraft.question),
    question: activeReadingDraft.question,
    answer: activeReadingDraft.answer,
    savedAt: new Date().toISOString()
  };

  const savedReadings = getSavedReadings();
  savedReadings.unshift(savedReading);
  saveState();
  renderSavedReadings();
  markReadingButtonSaved(activeReadingDraft.id, category);
  closeSaveReadingDialog();
  showSaveToast(`Saved under ${category}.`);
}

function renderSavedReadings() {
  const list = document.querySelector("[data-reading-list]");
  if (!list) return;

  const savedReadings = getSavedReadings();
  renderChartSavedReadings(savedReadings);
  list.textContent = "";

  if (!savedReadings.length) {
    defaultReadingCategories.forEach((category) => {
      list.appendChild(createReadingCard({
        category: category.name,
        title: category.title,
        body: category.body
      }));
    });
    return;
  }

  getReadingCategoryNames().forEach((category) => {
    const readings = savedReadings.filter((reading) => reading.category === category);
    if (!readings.length) return;

    const group = document.createElement("section");
    group.className = "reading-category-group";

    const heading = document.createElement("div");
    heading.className = "reading-category-heading";

    const title = document.createElement("span");
    title.textContent = category;

    const count = document.createElement("small");
    count.textContent = `${readings.length} saved`;

    heading.append(title, count);
    group.appendChild(heading);
    readings.forEach((reading) => group.appendChild(createReadingCard(reading, true)));
    list.appendChild(group);
  });
}

function renderChartSavedReadings(savedReadings) {
  const list = document.querySelector("[data-chart-saved-reading-list]");
  const count = document.querySelector("[data-chart-saved-reading-count]");
  if (!list) return;

  list.textContent = "";
  if (count) {
    count.textContent = `${savedReadings.length} saved ${savedReadings.length === 1 ? "reading" : "readings"}`;
  }

  if (!savedReadings.length) {
    const empty = document.createElement("article");
    empty.className = "chart-saved-reading-empty";

    const title = document.createElement("strong");
    title.textContent = "No saved readings yet";

    const copy = document.createElement("p");
    copy.textContent = "Save guidance from Ask and it will appear here beside your chart profiles.";

    empty.append(title, copy);
    list.appendChild(empty);
    return;
  }

  savedReadings.slice(0, 3).forEach((reading) => {
    const card = document.createElement("article");
    card.className = "chart-saved-reading";
    card.dataset.openSavedReading = reading.id;
    card.setAttribute("role", "button");
    card.setAttribute("tabindex", "0");
    card.setAttribute("aria-haspopup", "dialog");
    card.setAttribute("aria-controls", "saved-reading-viewer-title");
    card.setAttribute("aria-label", `Open saved reading: ${reading.title}`);

    const category = document.createElement("span");
    category.textContent = reading.category || "Saved Reading";

    const title = document.createElement("strong");
    title.textContent = reading.title || "Oracle Reading";

    const date = document.createElement("small");
    date.textContent = `Saved ${formatReadingDate(reading.savedAt)}`;

    card.append(category, title, date);
    list.appendChild(card);
  });
}

function createReadingCard(reading, isSaved = false) {
  const card = document.createElement("article");
  card.className = isSaved ? "reading-card saved-reading-card" : "reading-card";

  const category = document.createElement("span");
  category.textContent = reading.category;

  const title = document.createElement("h3");
  title.textContent = reading.title;

  const body = document.createElement("p");
  body.textContent = isSaved ? reading.question : reading.body;

  card.append(category, title, body);

  if (isSaved) {
    card.dataset.openSavedReading = reading.id;
    card.setAttribute("role", "button");
    card.setAttribute("tabindex", "0");
    card.setAttribute("aria-haspopup", "dialog");
    card.setAttribute("aria-controls", "saved-reading-viewer-title");
    card.setAttribute("aria-label", `Open saved reading: ${reading.title}`);

    const answer = document.createElement("p");
    answer.className = "saved-reading-answer";
    answer.textContent = truncateText(reading.answer, 150);

    const date = document.createElement("small");
    date.className = "saved-reading-date";
    date.textContent = `Saved ${formatReadingDate(reading.savedAt)}`;

    const openLabel = document.createElement("span");
    openLabel.className = "saved-reading-open";
    openLabel.textContent = "Open reading";

    card.append(answer, date, openLabel);
  }

  return card;
}

function openSavedReading(readingId) {
  const reading = getSavedReadings().find((item) => item.id === readingId);
  if (!reading || !savedReadingViewer || !savedReadingViewerContent) return;

  if (savedReadingViewerCategory) savedReadingViewerCategory.textContent = reading.category || "Saved Reading";
  if (savedReadingViewerTitle) savedReadingViewerTitle.textContent = reading.title || "Your reading";
  if (savedReadingViewerQuestion) savedReadingViewerQuestion.textContent = reading.question || "";
  if (savedReadingViewerDate) {
    savedReadingViewerDate.textContent = `Saved ${formatReadingDate(reading.savedAt)}`;
  }

  savedReadingViewerContent.textContent = "";
  renderOracleMessageContent(savedReadingViewerContent, reading.answer || "This reading has no saved response.");

  if (typeof savedReadingViewer.showModal === "function") {
    savedReadingViewer.showModal();
  } else {
    savedReadingViewer.setAttribute("open", "");
  }

  if (savedReadingViewerInner) savedReadingViewerInner.scrollTop = 0;
}

function closeSavedReadingViewer() {
  if (savedReadingViewer?.open && typeof savedReadingViewer.close === "function") {
    savedReadingViewer.close();
  }
  savedReadingViewer?.removeAttribute("open");
}

function createReadingTitle(question) {
  const cleaned = String(question || "Oracle Reading")
    .replace(/\s+/g, " ")
    .replace(/[?.!]+$/g, "")
    .trim();

  return truncateText(cleaned || "Oracle Reading", 58);
}

function truncateText(text, limit) {
  const value = String(text || "").replace(/\s+/g, " ").trim();
  if (value.length <= limit) return value;
  return `${value.slice(0, limit - 1).trim()}…`;
}

function formatReadingDate(value) {
  const date = value ? new Date(value) : new Date();
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric"
  }).format(date);
}

function markReadingButtonSaved(draftId, category) {
  const button = document.querySelector(`[data-save-reading="${draftId}"]`);
  if (!button) return;

  button.textContent = "Saved";
  button.setAttribute("aria-label", `Saved to ${category}`);
  button.disabled = true;
  button.classList.add("saved");
}

function shareReading(draftId, platform) {
  const draft = readingDrafts.get(draftId);
  if (!draft) return;

  const shareText = getReadingShareText(draft);
  const shareUrl = `${window.location.origin}${window.location.pathname}#readings`;

  if (platform === "facebook") {
    openShareWindow(`https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(shareUrl)}&quote=${encodeURIComponent(shareText)}`);
    return;
  }

  if (platform === "x") {
    openShareWindow(`https://twitter.com/intent/tweet?text=${encodeURIComponent(truncateText(shareText, 210))}&url=${encodeURIComponent(shareUrl)}`);
    return;
  }

  if (platform === "instagram" || platform === "messenger") {
    copyShareText(shareText);
    showSaveToast(`Copied for ${platform === "instagram" ? "Instagram" : "Messenger"}.`);
    return;
  }

  if (navigator.share) {
    navigator.share({
      title: "Astromeg Oracle Reading",
      text: shareText,
      url: shareUrl
    }).catch(() => {});
    return;
  }

  copyShareText(shareText);
  showSaveToast("Copied reading to share.");
}

function getReadingShareText(draft) {
  return `Astromeg Oracle reading\n\n${draft.question}\n\n${truncateText(draft.answer, 260)}`;
}

function copyShareText(text) {
  navigator.clipboard?.writeText(text).catch(() => {});
}

function openShareWindow(url) {
  const opened = window.open(url, "_blank", "noopener,noreferrer");
  if (!opened) {
    window.location.assign(url);
  }
}

function showSaveToast(message) {
  if (!saveToast) return;

  saveToast.textContent = message;
  saveToast.hidden = false;
  window.clearTimeout(saveToastTimer);
  saveToastTimer = window.setTimeout(() => {
    saveToast.hidden = true;
  }, 2600);
}

function getRouteInfo(routeName) {
  const meditationChoice = meditationRoutes[routeName];
  if (meditationChoice) {
    setMeditationPlaylist(meditationChoice);
    return {
      screen: "guided-meditation",
      route: routeName
    };
  }

  const screenName = routeAliases[routeName] || routeName || "start";
  const hasScreen = screens.some((screen) => screen.dataset.screen === screenName);

  return {
    screen: hasScreen ? screenName : "start",
    route: hasScreen ? (routeName || screenName) : "start"
  };
}

function getInitialRoute() {
  const hash = window.location.hash.slice(1);
  return getRouteInfo(hash);
}

function syncRoute(routeName, push = true) {
  if (!routeName) return;
  const nextHash = `#${routeName}`;
  if (window.location.hash === nextHash) return;

  const nextUrl = `${window.location.pathname}${window.location.search}${nextHash}`;
  if (push) {
    window.history.pushState({ route: routeName }, "", nextUrl);
  } else {
    window.history.replaceState({ route: routeName }, "", nextUrl);
  }
}

function handleRouteChange() {
  const route = getInitialRoute();
  state.history = [route.screen];
  go(route.screen, false, route.route);
}

function formatAccessDate(date) {
  return new Intl.DateTimeFormat(undefined, {
    month: "long",
    day: "numeric",
    year: "numeric"
  }).format(date);
}

function parseAccessEndDate(value) {
  const rawValue = String(value || "").trim();
  if (!rawValue) return null;

  const dateOnlyMatch = rawValue.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (dateOnlyMatch) {
    const [, year, month, day] = dateOnlyMatch.map(Number);
    return new Date(year, month - 1, day, 23, 59, 59, 999);
  }

  const parsedDate = new Date(rawValue);
  return Number.isNaN(parsedDate.valueOf()) ? null : parsedDate;
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
  const checkoutButton = event.target.closest("[data-plan-checkout]");
  if (checkoutButton) {
    startPlanCheckout(checkoutButton.dataset.planCheckout, checkoutButton);
    return;
  }

  if (event.target.closest("[data-onboarding-next]")) {
    advanceOnboarding();
    return;
  }

  const themeChoiceButton = event.target.closest("[data-theme-choice]");
  if (themeChoiceButton) {
    setThemePreference(themeChoiceButton.dataset.themeChoice);
    return;
  }

  if (event.target.closest("[data-theme-toggle]")) {
    toggleThemePreference();
    return;
  }

  if (event.target.closest("[data-today-sky-notification-toggle]")) {
    toggleTodaySkyNotifications();
    return;
  }

  const onboardingDot = event.target.closest("[data-onboarding-dot]");
  if (onboardingDot) {
    setOnboardingSlide(Number(onboardingDot.dataset.onboardingDot) || 0);
    return;
  }

  if (event.target.closest("[data-zodiac-prev]")) {
    shiftZodiacPlaylist(-1);
    return;
  }

  if (event.target.closest("[data-zodiac-next]")) {
    shiftZodiacPlaylist(1);
    return;
  }

  const playlistSignButton = event.target.closest("[data-playlist-sign]");
  if (playlistSignButton) {
    setZodiacPlaylist(playlistSignButton.dataset.playlistSign);

    if (playlistSignButton.classList.contains("zodiac-playlist-card")) {
      go("zodiac-playlist");
    }

    return;
  }

  if (event.target.closest("[data-playlist-listen]")) {
    event.preventDefault();
    openZodiacPlaylistLink();
    return;
  }

  if (event.target.closest("[data-playlist-ask]")) {
    const playlist = zodiacPlaylists[activeZodiacIndex];
    const questionInput = document.querySelector("[data-ask-form] input");
    if (questionInput) questionInput.value = playlist.prompt;
    state.chatMode = "default";
    go("ask");
    return;
  }

  const meditationChoiceButton = event.target.closest("[data-meditation-choice]");
  if (meditationChoiceButton) {
    openMeditationPage(meditationChoiceButton.dataset.meditationChoice);
    return;
  }

  const readingMenuButton = event.target.closest("[data-reading-menu-choice]");
  if (readingMenuButton) {
    const prompt = readingMenuButton.dataset.fillPrompt;
    if (prompt) submitOracleQuestion(prompt);
    return;
  }

  const catalogReadingButton = event.target.closest("[data-catalog-reading]");
  if (catalogReadingButton) {
    const readingTitle = catalogReadingButton.dataset.catalogReading;
    const reading = oracleReadingCatalog.find((item) => item.title === readingTitle);
    if (!reading) return;

    const access = getReadingAccessContext();
    if (isReadingUnlocked(reading, access)) {
      submitOracleQuestion(reading.prompt);
    } else {
      openUnlockReadingDialog(reading, access);
    }
    return;
  }

  const loveChoiceButton = event.target.closest("[data-love-choice]");
  if (loveChoiceButton) {
    const prompt = loveChoiceButton.dataset.fillPrompt;
    if (prompt) submitOracleQuestion(prompt);
    return;
  }

  const moneyChoiceButton = event.target.closest("[data-money-choice]");
  if (moneyChoiceButton) {
    const prompt = moneyChoiceButton.dataset.fillPrompt;
    if (prompt) submitOracleQuestion(prompt);
    return;
  }

  const timingChoiceButton = event.target.closest("[data-timing-choice]");
  if (timingChoiceButton) {
    const prompt = timingChoiceButton.dataset.fillPrompt;
    if (prompt) submitOracleQuestion(prompt);
    return;
  }

  const karmaChoiceButton = event.target.closest("[data-karma-choice]");
  if (karmaChoiceButton) {
    const prompt = karmaChoiceButton.dataset.fillPrompt;
    if (prompt) submitOracleQuestion(prompt);
    return;
  }

  const saveReadingButton = event.target.closest("[data-save-reading]");
  if (saveReadingButton) {
    openSaveReadingDialog(saveReadingButton.dataset.saveReading);
    return;
  }

  const savedReadingCard = event.target.closest("[data-open-saved-reading]");
  if (savedReadingCard) {
    openSavedReading(savedReadingCard.dataset.openSavedReading);
    return;
  }

  const shareReadingButton = event.target.closest("[data-share-reading]");
  if (shareReadingButton) {
    shareReading(shareReadingButton.dataset.shareReading, shareReadingButton.dataset.sharePlatform || "native");
    return;
  }

  const lessonLevelButton = event.target.closest("[data-lesson-level]");
  if (lessonLevelButton) {
    openLessonDialog(lessonLevelButton.dataset.lessonLevel);
    return;
  }

  if (event.target.closest("[data-open-person-dialog]")) {
    openPersonChartDialog();
    return;
  }

  const removePersonButton = event.target.closest("[data-remove-person]");
  if (removePersonButton) {
    removeSavedPerson(removePersonButton.dataset.removePerson);
    return;
  }

  const dailyButton = event.target.closest("[data-daily-popup]");
  if (dailyButton) {
    openDailyDialog(dailyButton);
    return;
  }

  const button = event.target.closest("[data-go]");
  if (!button) return;

  if (button.dataset.go === "ask") {
    state.chatMode = button.dataset.chatMode || "default";
  }

  const prompt = button.dataset.fillPrompt;
  const questionInput = document.querySelector("[data-ask-form] input");

  if (button.dataset.go === "ask" && (state.chatMode === "love" || state.chatMode === "money" || state.chatMode === "timing" || state.chatMode === "karma")) {
    if (questionInput) questionInput.value = "";
  }

  if (prompt) {
    if (questionInput) questionInput.value = prompt;
  }

  go(button.dataset.go);
});

dailyDialogClose?.addEventListener("click", closeDailyDialog);

dailyDialog?.addEventListener("click", (event) => {
  if (event.target === dailyDialog) closeDailyDialog();
});

lessonDialogClose?.addEventListener("click", closeLessonDialog);

lessonDialog?.addEventListener("click", (event) => {
  if (event.target === lessonDialog) closeLessonDialog();
});

beginLessonButton?.addEventListener("click", beginLesson);

dailyDialogAsk?.addEventListener("click", () => {
  const questionInput = document.querySelector("[data-ask-form] input");
  if (questionInput && activeDailyPrompt) questionInput.value = activeDailyPrompt;
  closeDailyDialog();
  state.chatMode = "default";
  go("ask");
});

saveReadingClose?.addEventListener("click", closeSaveReadingDialog);

saveReadingDialog?.addEventListener("click", (event) => {
  if (event.target === saveReadingDialog) closeSaveReadingDialog();
});

unlockReadingDialog?.addEventListener("click", (event) => {
  if (event.target === unlockReadingDialog || event.target.closest("[data-unlock-reading-close]")) {
    closeUnlockReadingDialog();
  }
});

unlockReadingDialog?.addEventListener("close", () => {
  activeLockedReading = null;
});

unlockReadingAction?.addEventListener("click", proceedToUnlockReading);

savedReadingViewerClose?.addEventListener("click", closeSavedReadingViewer);

savedReadingViewer?.addEventListener("click", (event) => {
  if (event.target === savedReadingViewer) closeSavedReadingViewer();
});

saveReadingCategory?.addEventListener("change", updateCustomCategoryField);

saveReadingForm?.addEventListener("submit", (event) => {
  event.preventDefault();
  saveActiveReading();
});

personChartClose?.addEventListener("click", closePersonChartDialog);

personChartDialog?.addEventListener("click", (event) => {
  if (event.target === personChartDialog) closePersonChartDialog();
});

journalForm?.addEventListener("submit", (event) => {
  event.preventDefault();
  saveJournalEntry(event.currentTarget);
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

  const savedReadingCard = event.target.closest?.("[data-open-saved-reading]");
  if (!savedReadingCard || (event.key !== "Enter" && event.key !== " ")) return;

  event.preventDefault();
  openSavedReading(savedReadingCard.dataset.openSavedReading);
});

window.addEventListener("hashchange", handleRouteChange);
window.addEventListener("popstate", handleRouteChange);

backButton.addEventListener("click", () => {
  state.history.pop();
  const previous = state.history[state.history.length - 1] || "start";
  go(previous, false);
});

googleSignInFallback?.addEventListener("click", () => {
  if (globalThis.google?.accounts?.id) {
    globalThis.google.accounts.id.prompt();
    setSignInStatus("Choose your Google account to continue.", "ready");
    return;
  }

  initializeGoogleSignIn();
});

document.querySelector("[data-access-code-open]")?.addEventListener("click", openAccessCodeDialog);

document.querySelectorAll("[data-access-code-close]").forEach((button) => {
  button.addEventListener("click", closeAccessCodeDialog);
});

accessCodeDialog?.addEventListener("click", (event) => {
  if (event.target === accessCodeDialog) closeAccessCodeDialog();
});

accessCodeForm?.addEventListener("submit", (event) => {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  const accessCode = String(form.get("accessCode") || "").trim();

  if (!accessCode) {
    setAccessCodeStatus("Enter your Oracle access code.", "error");
    return;
  }

  authenticateAccessCode(accessCode);
});

document.querySelector("[data-activate-form]").addEventListener("submit", (event) => {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  const email = String(form.get("email") || "").trim();

  if (!email) {
    setEmailSignInStatus("Enter the email connected to your Oracle account.", "error");
    return;
  }

  authenticateEmail(email, event.currentTarget);
});

document.querySelector("[data-birth-form]").addEventListener("submit", (event) => {
  event.preventDefault();
  const form = new FormData(event.currentTarget);

  state.profile.name = String(form.get("name") || "").trim();
  state.profile.birthDate = form.get("birthDate");
  state.profile.birthTime = form.get("birthTime");
  state.profile.birthCity = String(form.get("birthCity") || "").trim();
  state.profile.birthCountry = String(form.get("birthCountry") || "").trim();
  state.profile.birthPlace = getBirthPlace();
  saveState();
  go("home");
});

document.querySelector("[data-chart-profile-form]")?.addEventListener("submit", (event) => {
  event.preventDefault();
  const form = new FormData(event.currentTarget);

  state.profile.name = String(form.get("name") || "").trim();
  state.profile.birthDate = form.get("birthDate");
  state.profile.birthTime = form.get("birthTime");
  state.profile.birthCity = String(form.get("birthCity") || "").trim();
  state.profile.birthCountry = String(form.get("birthCountry") || "").trim();
  state.profile.birthPlace = getBirthPlace();
  saveState();
  updateProfile();
  showSaveToast("Chart details saved.");
});

document.querySelector("[data-saved-person-form]")?.addEventListener("submit", (event) => {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  const savedPeople = getSavedPeopleCharts();

  savedPeople.unshift({
    id: `person-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    name: String(form.get("personName") || "").trim(),
    connection: String(form.get("personConnection") || "").trim(),
    birthDate: form.get("personBirthDate"),
    birthTime: form.get("personBirthTime"),
    birthCity: String(form.get("personBirthCity") || "").trim(),
    birthCountry: String(form.get("personBirthCountry") || "").trim(),
    savedAt: new Date().toISOString()
  });

  saveState();
  event.currentTarget.reset();
  closePersonChartDialog();
  renderSavedPeople();
  showSaveToast("Profile saved to My Chart.");
});

document.querySelector("[data-ask-form]").addEventListener("submit", (event) => {
  event.preventDefault();
  const input = event.currentTarget.elements.question;
  const question = input.value.trim();
  if (!question) return;

  submitOracleQuestion(question);
  input.value = "";
});

function submitOracleQuestion(question) {
  appendMessage("You", question, "user");
  const thinkingMessage = appendMessage(
    "Astromeg Oracle",
    "Making contact with the cosmos...",
    "oracle",
    { waiting: true }
  );

  requestOracleAnswer(question)
    .then((response) => {
      removeOracleWaitingMessage(thinkingMessage);
      appendMessage(
        "Astromeg Oracle",
        response.answer,
        "oracle",
        { saveable: response.saveable, question, catalog: response.catalog }
      );
    })
    .catch((error) => {
      removeOracleWaitingMessage(thinkingMessage);
      document.documentElement.dataset.oracleChatError = String(error?.message || error);
      console.error("Oracle chat request failed:", error);
      appendMessage(
        "Astromeg Oracle",
        "The Oracle connection is momentarily unavailable. Please try your question again.",
        "oracle",
        { saveable: false, question }
      );
    });
}

function removeOracleWaitingMessage(message) {
  if (!message) return;
  if (message.oracleWaitingTimer) {
    window.clearInterval(message.oracleWaitingTimer);
  }
  message.remove();
}

function startOracleWaitingAnimation(message) {
  const label = message.querySelector("[data-oracle-waiting-label]");
  if (!label) return;
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

  const waitingPhrases = [
    "Making contact with the cosmos...",
    "Reading the pattern in your sky...",
    "Aligning your chart and timing...",
    "Preparing your Oracle reading..."
  ];
  let phraseIndex = 0;

  message.oracleWaitingTimer = window.setInterval(() => {
    phraseIndex = (phraseIndex + 1) % waitingPhrases.length;
    label.classList.remove("is-arriving");
    window.requestAnimationFrame(() => {
      label.textContent = waitingPhrases[phraseIndex];
      label.classList.add("is-arriving");
    });
  }, 2600);
}

async function requestOracleAnswer(question) {
  if (isAvailableReadingsRequest(question)) {
    return getOracleResponse(question);
  }

  const response = await fetch(oracleChatEndpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(createOracleChatPayload(question))
  });
  const data = await response.json().catch(() => ({}));
  const answer = String(data.answer || "").trim();

  if (!response.ok) {
    throw new Error(String(data.detail || data.message || `Oracle chat request failed (${response.status}).`));
  }

  if (!answer) {
    throw new Error("Oracle chat returned an empty answer.");
  }

  return {
    saveable: response.ok && data.success !== false,
    answer
  };
}

function createOracleChatPayload(question) {
  const previewAccessCode = new URLSearchParams(window.location.search).get("demo") || "";
  return {
    question,
    chat_mode: state.chatMode || "default",
    email: state.profile.email || "",
    customer_name: state.profile.customer_name || state.profile.name || "",
    access_code: state.profile.access_code || state.profile.accessCode || previewAccessCode,
    birth_profile: getOracleBirthProfilePayload(),
    chart: state.profile.chart || {},
    transits: state.profile.transits || {},
    saved_people: getSavedPeopleCharts().slice(0, 6),
    history: getOracleChatHistory()
  };
}

function getOracleBirthProfilePayload() {
  const [birthYear, birthMonth, birthDay] = String(state.profile.birthDate || "").split("-").map(Number);
  const [birthHour, birthMinute] = String(state.profile.birthTime || "").split(":").map(Number);
  return {
    name: state.profile.name || state.profile.customer_name || "",
    birth_date: state.profile.birthDate || "",
    birth_time: state.profile.birthTime || "",
    birth_year: Number.isFinite(birthYear) ? birthYear : null,
    birth_month: Number.isFinite(birthMonth) ? birthMonth : null,
    birth_day: Number.isFinite(birthDay) ? birthDay : null,
    birth_hour: Number.isFinite(birthHour) ? birthHour : null,
    birth_minute: Number.isFinite(birthMinute) ? birthMinute : null,
    birth_city: getBirthCity(),
    birth_country: getBirthCountry(),
    birthplace: getBirthPlace()
  };
}

function getOracleChatHistory() {
  const messages = Array.from(document.querySelectorAll("[data-chat-log] .message")).slice(-8);
  return messages.map((message) => ({
    role: message.classList.contains("user") ? "user" : "assistant",
    content: message.dataset.chatContent
      || message.querySelector(".message-reading-content")?.textContent
      || message.querySelector("p")?.textContent
      || ""
  })).filter((message) => message.content.trim());
}

function getOracleResponse(question) {
  if (isAvailableReadingsRequest(question)) {
    return {
      saveable: false,
      catalog: true,
      answer: "Choose a reading below. Your current access and every available reading are shown together."
    };
  }

  return {
    saveable: true,
    answer: "I would begin by checking the natal promise, current timing, and repeating pattern around this question. The next aligned step is to name the theme clearly, choose one deliberate action, and watch the dates that confirm the movement."
  };
}

function isAvailableReadingsRequest(question) {
  return /list all available readings and their purpose/i.test(String(question || ""));
}

function getReadingAccessContext() {
  const planId = String(state.profile.plan_id || state.profile.plan || "").trim();
  const configuredPlan = pricingConfig?.getPlan(planId);
  const accessCode = String(state.profile.access_code || state.profile.accessCode || "").trim().toUpperCase();
  const permissionLevel = String(state.profile.permission_level || "").trim();
  const readingType = String(state.profile.reading_type || "").trim();
  const isLegacyLocalDemoOverride = accessCode === "DEMO888"
    && permissionLevel.toUpperCase() === "ALL_ACCESS_ANNUAL"
    && readingType.toUpperCase() === "ALL_ACCESS_ANNUAL";
  const accountMarkers = [
    isLegacyLocalDemoOverride ? "DEMO" : permissionLevel,
    isLegacyLocalDemoOverride ? "DEMO" : readingType,
    state.profile.access_type
  ].filter(Boolean).join(" ").replace(/[_-]+/g, " ").toUpperCase();
  const isOwner = oracleOwnerEmails.has(
    String(state.profile.email || "").trim().toLowerCase()
  );
  const active = isOwner || getAccessPillState().active;
  const allAccessByMarker = /\b(ALL\s*ACCESS|FULL(?:\s*ACCESS)?|VIP|FOUNDER|INNER\s*CIRCLE|UNLIMITED)\b/.test(accountMarkers);
  const isAllAccess = configuredPlan?.all_access === true
    || state.profile.all_in_access === true
    || allAccessByMarker
    || isOwner;
  const isEssentialAnnual = planId === pricingConfig?.plan_ids?.ESSENTIAL_ANNUAL
    || configuredPlan?.benefits?.relationship_synastry_guidance_included === true;
  const isAllAccessAnnual = planId === pricingConfig?.plan_ids?.ALL_ACCESS_ANNUAL
    || /\bALL\s*ACCESS\s*ANNUAL\b/.test(accountMarkers)
    || isOwner;
  const isDemo = accessCode === "DEMO888" || /\bDEMO\b/.test(accountMarkers);
  const accessEndRaw = state.profile.access_end || state.profile.accessEnd || "";
  const accessEnd = parseAccessEndDate(accessEndRaw);
  const expirationLabel = accessEnd && !Number.isNaN(accessEnd.valueOf())
    ? `Expires ${formatAccessDate(accessEnd)}`
    : "";

  let accessLabel = "Oracle Essential";
  if (!active) accessLabel = "No active plan";
  else if (isAllAccessAnnual) accessLabel = "Oracle All Access Annual";
  else if (isAllAccess) accessLabel = "Oracle All Access";
  else if (isEssentialAnnual) accessLabel = "Oracle Essential Annual";
  else if (isDemo) accessLabel = "Oracle Essential Demo";

  return {
    active,
    isAllAccess,
    isAllAccessAnnual,
    isEssentialAnnual,
    accessLabel,
    expirationLabel
  };
}

function isReadingUnlocked(reading, access) {
  if (!access.active) return false;
  if (reading.tier === "essential") return true;
  if (reading.tier === "essential_annual") {
    return access.isEssentialAnnual || access.isAllAccess;
  }
  if (reading.tier === "all_access") return access.isAllAccess;
  if (reading.tier === "all_access_annual") return access.isAllAccessAnnual;
  return false;
}

function getRequiredReadingAccessLabel(reading) {
  const labels = {
    essential: "Oracle Essential",
    essential_annual: "Oracle Essential Annual",
    all_access: "Oracle All Access",
    all_access_annual: "Oracle All Access Annual"
  };

  return labels[reading?.tier] || reading?.tierLabel || "an eligible Oracle plan";
}

function openUnlockReadingDialog(reading, access = getReadingAccessContext()) {
  if (!reading || !unlockReadingDialog) return;

  activeLockedReading = reading;
  if (unlockReadingTitle) unlockReadingTitle.textContent = reading.title;
  if (unlockReadingPurpose) unlockReadingPurpose.textContent = reading.purpose;
  if (unlockReadingCurrentAccess) unlockReadingCurrentAccess.textContent = access.accessLabel;
  if (unlockReadingRequiredAccess) {
    unlockReadingRequiredAccess.textContent = `Included with ${getRequiredReadingAccessLabel(reading)}`;
  }

  if (typeof unlockReadingDialog.showModal === "function") {
    unlockReadingDialog.showModal();
  } else {
    unlockReadingDialog.setAttribute("open", "");
  }
}

function closeUnlockReadingDialog() {
  activeLockedReading = null;
  if (unlockReadingDialog?.open && typeof unlockReadingDialog.close === "function") {
    unlockReadingDialog.close();
  }
  unlockReadingDialog?.removeAttribute("open");
}

function proceedToUnlockReading() {
  if (!activeLockedReading) return;

  const reading = activeLockedReading;
  const requiredAccess = getRequiredReadingAccessLabel(reading);
  closeUnlockReadingDialog();
  go("pricing");
  setCheckoutStatus(
    `${reading.title} is included with ${requiredAccess}. Choose the eligible plan below to unlock it.`,
    "ready"
  );
}

function appendReadingCatalog(message) {
  const access = getReadingAccessContext();
  const catalog = document.createElement("div");
  catalog.className = "reading-catalog";

  const accessSummary = document.createElement("div");
  accessSummary.className = "reading-catalog-access";
  accessSummary.innerHTML = "<span>Your access</span><strong></strong>";
  accessSummary.querySelector("span").textContent = access.expirationLabel
    ? `Your access · ${access.expirationLabel}`
    : "Your access";
  accessSummary.querySelector("strong").textContent = access.accessLabel;
  catalog.appendChild(accessSummary);

  const list = document.createElement("div");
  list.className = "reading-catalog-list";

  oracleReadingCatalog.forEach((reading) => {
    const unlocked = isReadingUnlocked(reading, access);
    const button = document.createElement("button");
    button.type = "button";
    button.className = "reading-catalog-item";
    button.setAttribute("aria-label", `Open ${reading.title}`);
    button.dataset.catalogReading = reading.title;
    button.dataset.readingUnlocked = String(unlocked);
    if (!unlocked) button.setAttribute("aria-haspopup", "dialog");

    const copy = document.createElement("span");
    copy.className = "reading-catalog-copy";
    copy.innerHTML = "<strong></strong><small></small>";
    copy.querySelector("strong").textContent = reading.title;
    copy.querySelector("small").textContent = reading.purpose;

    const action = document.createElement("span");
    action.className = "reading-catalog-action";
    action.textContent = "Open";

    button.append(copy, action);
    list.appendChild(button);
  });

  catalog.appendChild(list);
  message.appendChild(catalog);
}

function removeSavedPerson(personId) {
  const savedPeople = getSavedPeopleCharts();
  state.profile.savedPeopleCharts = savedPeople.filter((person) => person.id !== personId);
  saveState();
  renderSavedPeople();
  showSaveToast("Person removed.");
}

function appendReadingInlineText(target, text) {
  const parts = String(text || "").split(/(\*\*[^*]+\*\*|\*[^*]+\*)/g);
  parts.forEach((part) => {
    if (!part) return;
    if (part.startsWith("**") && part.endsWith("**")) {
      const strong = document.createElement("strong");
      strong.textContent = part.slice(2, -2);
      target.appendChild(strong);
      return;
    }
    if (part.startsWith("*") && part.endsWith("*")) {
      const emphasis = document.createElement("em");
      emphasis.textContent = part.slice(1, -1);
      target.appendChild(emphasis);
      return;
    }
    target.appendChild(document.createTextNode(part));
  });
}

function parseReadingTableRow(line) {
  const normalized = String(line || "").trim().replace(/^\|/, "").replace(/\|$/, "");
  if (!normalized.includes("|")) return [];
  return normalized.split("|").map((cell) => cell.trim());
}

function isReadingTableDivider(line) {
  const cells = parseReadingTableRow(line);
  return cells.length > 1 && cells.every((cell) => /^:?-{3,}:?$/.test(cell));
}

function createReadingTable(headers, rows, label = "Astrology chart data") {
  const wrapper = document.createElement("div");
  wrapper.className = "reading-table-wrap";

  const table = document.createElement("table");
  table.className = "reading-data-table";
  table.setAttribute("aria-label", label);

  const tableHead = document.createElement("thead");
  const headingRow = document.createElement("tr");
  headers.forEach((header) => {
    const cell = document.createElement("th");
    cell.scope = "col";
    appendReadingInlineText(cell, header);
    headingRow.appendChild(cell);
  });
  tableHead.appendChild(headingRow);

  const tableBody = document.createElement("tbody");
  rows.forEach((row) => {
    const tableRow = document.createElement("tr");
    headers.forEach((_, index) => {
      const cell = document.createElement("td");
      appendReadingInlineText(cell, row[index] || "—");
      tableRow.appendChild(cell);
    });
    tableBody.appendChild(tableRow);
  });

  table.append(tableHead, tableBody);
  wrapper.appendChild(table);
  return wrapper;
}

function formatHouseNumber(value) {
  const house = String(value || "").trim();
  if (!house) return "—";
  if (/[a-z]/i.test(house)) return house;
  const number = Number(house);
  if (!Number.isFinite(number)) return house;
  const remainder = number % 100;
  if (remainder >= 11 && remainder <= 13) return `${number}th`;
  const suffix = number % 10 === 1 ? "st" : number % 10 === 2 ? "nd" : number % 10 === 3 ? "rd" : "th";
  return `${number}${suffix}`;
}

function parseAstrologyPlacementLine(line) {
  const normalized = String(line || "").trim().replace(/^[-*•]\s*/, "");
  const match = normalized.match(
    /^(Sun|Moon|Mercury|Venus|Mars|Jupiter|Saturn|Uranus|Neptune|Pluto|North Node|South Node|True Node|Mean Node|Chiron|Ascendant|ASC|Midheaven|MC|Descendant|IC)\s*(?::|—|–|-|\bin\b)?\s*(Aries|Taurus|Gemini|Cancer|Leo|Virgo|Libra|Scorpio|Sagittarius|Capricorn|Aquarius|Pisces)\s*(?:at\s*)?(\d{1,3}(?:\.\d+)?°(?:\s*\d{1,2}(?:['′])?)?)\s*(?:R|Rx|℞)?(?:\s*(?:[,;]|—|–|-|\bin(?:\s+the)?\b)\s*(?:(?:House\s*)?(\d{1,2}(?:st|nd|rd|th)?)(?:\s*House)?))?$/i
  );
  if (!match) return null;
  return [match[1], match[2], match[3], formatHouseNumber(match[4])];
}

function isReadingStructureLine(lines, index) {
  const line = String(lines[index] || "").trim();
  const nextLine = String(lines[index + 1] || "").trim();
  return /^#{1,4}\s+/.test(line)
    || /^[-*•]\s+/.test(line)
    || /^\d+[.)]\s+/.test(line)
    || (line.includes("|") && isReadingTableDivider(nextLine))
    || Boolean(parseAstrologyPlacementLine(line));
}

function renderOracleMessageContent(container, text) {
  const lines = String(text || "").replace(/\r\n?/g, "\n").split("\n");
  let index = 0;

  while (index < lines.length) {
    const line = lines[index].trim();
    if (!line) {
      index += 1;
      continue;
    }

    if (line.includes("|") && isReadingTableDivider(lines[index + 1])) {
      const headers = parseReadingTableRow(line);
      const rows = [];
      index += 2;
      while (index < lines.length) {
        const row = parseReadingTableRow(lines[index]);
        if (row.length < 2 || isReadingTableDivider(lines[index])) break;
        rows.push(row);
        index += 1;
      }
      if (rows.length) {
        container.appendChild(createReadingTable(headers, rows, headers.join(", ")));
        continue;
      }
    }

    const headingMatch = line.match(/^(#{1,4})\s+(.+)$/);
    if (headingMatch) {
      const heading = document.createElement(headingMatch[1].length <= 2 ? "h3" : "h4");
      appendReadingInlineText(heading, headingMatch[2]);
      container.appendChild(heading);
      index += 1;
      continue;
    }

    const placement = parseAstrologyPlacementLine(line);
    if (placement) {
      const rows = [];
      while (index < lines.length) {
        const row = parseAstrologyPlacementLine(lines[index]);
        if (!row) break;
        rows.push(row);
        index += 1;
      }
      container.appendChild(
        createReadingTable(["Planet", "Sign", "Degree", "House"], rows, "Planetary placements")
      );
      continue;
    }

    const bulletMatch = line.match(/^[-*•]\s+(.+)$/);
    if (bulletMatch) {
      const list = document.createElement("ul");
      while (index < lines.length) {
        const itemMatch = lines[index].trim().match(/^[-*•]\s+(.+)$/);
        if (!itemMatch) break;
        const item = document.createElement("li");
        appendReadingInlineText(item, itemMatch[1]);
        list.appendChild(item);
        index += 1;
      }
      container.appendChild(list);
      continue;
    }

    const numberedMatch = line.match(/^\d+[.)]\s+(.+)$/);
    if (numberedMatch) {
      const list = document.createElement("ol");
      while (index < lines.length) {
        const itemMatch = lines[index].trim().match(/^\d+[.)]\s+(.+)$/);
        if (!itemMatch) break;
        const item = document.createElement("li");
        appendReadingInlineText(item, itemMatch[1]);
        list.appendChild(item);
        index += 1;
      }
      container.appendChild(list);
      continue;
    }

    const paragraphLines = [line];
    index += 1;
    while (
      index < lines.length
      && lines[index].trim()
      && !isReadingStructureLine(lines, index)
    ) {
      paragraphLines.push(lines[index].trim());
      index += 1;
    }
    const paragraph = document.createElement("p");
    appendReadingInlineText(paragraph, paragraphLines.join(" "));
    container.appendChild(paragraph);
  }
}

function appendMessage(author, text, type, options = {}) {
  const log = document.querySelector("[data-chat-log]");
  const message = document.createElement("div");
  message.className = `message ${type}`;
  message.dataset.chatContent = text;
  const authorLabel = document.createElement("span");
  authorLabel.textContent = author;
  message.appendChild(authorLabel);

  if (type === "oracle") {
    const readingContent = document.createElement("div");
    readingContent.className = "message-reading-content";
    if (options.waiting) {
      message.classList.add("oracle-waiting-message");
      readingContent.classList.add("oracle-waiting-content");
      readingContent.innerHTML = `
        <div class="oracle-constellation" aria-hidden="true">
          <span class="oracle-star oracle-star-one">✦</span>
          <span class="oracle-star oracle-star-two">✧</span>
          <span class="oracle-star oracle-star-three">✦</span>
          <span class="oracle-star oracle-star-four">✧</span>
          <span class="oracle-star oracle-star-five">✦</span>
        </div>
        <div class="oracle-waiting-copy" role="status" aria-live="polite">
          <p class="oracle-waiting-title is-arriving" data-oracle-waiting-label>Making contact with the cosmos...</p>
          <p class="oracle-waiting-note">Calculating your chart and weaving the reading.</p>
        </div>
      `;
    } else {
      renderOracleMessageContent(readingContent, text);
    }
    message.appendChild(readingContent);
  } else {
    const paragraph = document.createElement("p");
    paragraph.textContent = text;
    message.appendChild(paragraph);
  }

  if (options.catalog) {
    message.classList.add("reading-catalog-message");
    appendReadingCatalog(message);
  }

  if (options.saveable) {
    const draft = createReadingDraft(options.question, text);
    const actions = document.createElement("div");
    actions.className = "message-actions";

    const saveButton = document.createElement("button");
    saveButton.className = "save-reading-button";
    saveButton.type = "button";
    saveButton.dataset.saveReading = draft.id;
    saveButton.textContent = "Save";

    const shareButton = document.createElement("button");
    shareButton.className = "share-reading-button";
    shareButton.type = "button";
    shareButton.dataset.shareReading = draft.id;
    shareButton.dataset.sharePlatform = "native";
    shareButton.textContent = "Share";

    const socialActions = document.createElement("div");
    socialActions.className = "social-share-actions";
    [
      ["facebook", "f", "Share to Facebook"],
      ["instagram", "◎", "Copy for Instagram"],
      ["x", "X", "Share to X"],
      ["messenger", "lightning", "Copy for Messenger"]
    ].forEach(([platform, icon, label]) => {
      const socialButton = document.createElement("button");
      socialButton.className = "social-share-button";
      socialButton.type = "button";
      socialButton.dataset.shareReading = draft.id;
      socialButton.dataset.sharePlatform = platform;
      socialButton.setAttribute("aria-label", label);
      socialButton.innerHTML = platform === "messenger"
        ? `<svg class="messenger-lightning-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M13.1 2.8 5.8 13h4.8l-1.2 8.2 8.8-11.7h-5.1l1.4-6.7h-1.4Z"/></svg>`
        : icon;
      socialActions.appendChild(socialButton);
    });

    actions.append(saveButton, shareButton, socialActions);
    message.appendChild(actions);
  }

  log.appendChild(message);
  message.scrollIntoView({ behavior: "smooth", block: options.catalog ? "start" : "end" });
  if (options.waiting) {
    startOracleWaitingAnimation(message);
  }
  return message;
}

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    window.scrollTo({ top: 0, left: 0, behavior: "instant" });
    navigator.serviceWorker.register("./sw.js?v=owner-all-access-v1")
      .then((registration) => registration.update())
      .catch(() => {});
  });
}

if ("scrollRestoration" in window.history) {
  window.history.scrollRestoration = "manual";
}

window.scrollTo({ top: 0, left: 0, behavior: "instant" });
setThemePreference(loadThemePreference(), false);
updateTodaySkyNotificationStatus();
renderPricing();
initializeGoogleSignIn();
setZodiacPlaylist("aries");
setMeditationPlaylist("healing");
const initialRoute = getInitialRoute();
state.history = [initialRoute.screen];
go(initialRoute.screen, false, initialRoute.route);
