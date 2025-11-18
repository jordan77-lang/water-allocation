// Preload sounds
const sounds = {
  food: new Audio("../sounds/food.mp3"),
  ai: new Audio("../sounds/ai.mp3"),
  crops: new Audio("../sounds/crops.mp3"),
  animals: new Audio("../sounds/animals.mp3")
};

// === Water animation tuning ===
const SOUND_THRESHOLD = 5; // minimum water-point jump to count as a bag event; keep slightly below the light bag increment from the backend
const SMALL_BAG_POINTS = 10; // mirror LIGHT_BAG_INCREMENT in backend/server.py when you recalibrate
const LARGE_BAG_POINTS = 25; // mirror HEAVY_BAG_INCREMENT in backend/server.py when you recalibrate
const STORY_DURATION = 6000; // ms that a story panel stays visible after a bag event

// === Decay controls ===
// Raise DECAY_RATE (closer to 1.0) to make the bar fall faster; lower it for a slower drain.
// Increase MIN_DECAY_STEP if small differences take too long to disappear.
// DECAY_INTERVAL_MS is how often the decay loop runs; shorten for smoother animation, lengthen to reduce CPU work.
// Remember to keep the backend DECAY_POINTS_PER_SECOND value in server.py in sync so the sensor-driven totals fall at a similar pace.
const DECAY_RATE = 0.005; // amount of water to drain toward the actual total each decay step (0.0 – 1.0 range)
const MIN_DECAY_STEP = 2; // smallest amount of water to remove each step so the drain animation stays visible
const DECAY_INTERVAL_MS = 2000; // how often the front-end water levels should decay (ms)
const MAX_WATER_POINTS = 200; // keep in sync with the backend: raise if the scene should allow more stored water

let lastValues = {food:0, ai:0, crops:0, animals:0};
const displayValues = {food:0, ai:0, crops:0, animals:0};

let testMode = false;
const bagButtons = document.querySelectorAll('.bag-button');

const storyArea = document.getElementById('story-area');
const storyHeading = document.getElementById('story-heading');
const storyBody = document.getElementById('story-body');
const bucketTitles = {food: 'Food', ai: 'AI', crops: 'Crops', animals: 'Animals'};

const stories = {
  food: [
    "Families gather to share corn stew, honoring the sunrise songs.",
    "Elders pass down recipes that stretch precious water further.",
    "A young farmer blesses the fields before preparing the meal.",
    "Food bundles travel to relatives who live beyond the mesas."
  ],
  ai: [
    "Students learn to code water-saving alerts in Diné Bizaad.",
    "Sensors monitor wells, sharing data across the chapter house.",
    "Youth engineers design solar pumps to respect the aquifer.",
    "Digital maps trace where water once flowed after the summer rains."
  ],
  crops: [
    "Corn pollen is offered as the fields drink before dawn.",
    "Beans climb the trellis, weaving green stories with the wind.",
    "A grandmother checks the soil, remembering floods and droughts.",
    "The sacred corn song rises as irrigation lines begin to whisper."
  ],
  animals: [
    "Sheep graze along the arroyo, hooves stirring ancient trails.",
    "A child refills the trough, promising to watch the clouds closely.",
    "Horse caretakers braid manes, thanking the animals for their labor.",
    "Water drums echo near the corral, calming the restless herd."
  ]
};

const lastStoryIndex = {food:null, ai:null, crops:null, animals:null};
let storyTimeout = null;

bagButtons.forEach((button) => {
  const bucket = button.dataset.bucket;
  const size = button.dataset.size;
  if (!bucket || !size) {
    return;
  }
  button.addEventListener('click', () => {
    testMode = true;
    const increment = size === 'large' ? LARGE_BAG_POINTS : SMALL_BAG_POINTS;
    const current = displayValues[bucket] || 0;
    const nextValue = Math.min(MAX_WATER_POINTS, current + increment);
    updateBar(bucket, nextValue, { targetValue: 0 });
  });
});

function getFillElement(key) {
  const bar = document.getElementById(key);
  if (!bar) {
    return null;
  }
  let fill = bar.querySelector('.fill');
  if (!fill) {
    fill = document.createElement('div');
    fill.className = 'fill';
    bar.appendChild(fill);
    for (let i = 0; i < 5; i++) {
      const bubble = document.createElement('div');
      bubble.className = 'bubble';
      fill.appendChild(bubble);
    }
  }
  return fill;
}

function setFillHeight(key, fillElement) {
  const fill = fillElement || getFillElement(key);
  if (!fill) {
    return;
  }
  const percent = Math.min((displayValues[key] / MAX_WATER_POINTS) * 100, 100);
  fill.style.height = percent + "%";
}

function updateBar(key, value, options = {}) {
  const fill = getFillElement(key);
  if (!fill) {
    return;
  }

  if (value > displayValues[key]) {
    displayValues[key] = value;
  }
  setFillHeight(key, fill);

  const previousTarget = lastValues[key] || 0;
  const diff = value - previousTarget;
  if (diff >= SOUND_THRESHOLD) {
    sounds[key].currentTime = 0;
    sounds[key].play();
    showStory(key);
  }

  const newTarget = Object.prototype.hasOwnProperty.call(options, 'targetValue')
    ? options.targetValue
    : value;
  lastValues[key] = Math.max(0, newTarget);
}

setInterval(() => {
  for (const key of Object.keys(displayValues)) {
    const target = lastValues[key] || 0;
    const current = displayValues[key];
    if (current > target) {
      const diff = current - target;
      const decayAmount = Math.max(diff * DECAY_RATE, MIN_DECAY_STEP);
      displayValues[key] = Math.max(target, current - decayAmount);
      setFillHeight(key);
    }
  }
}, DECAY_INTERVAL_MS);

function showStory(key) {
  const options = stories[key] || [];
  if (options.length === 0) {
    return;
  }
  let index = Math.floor(Math.random() * options.length);
  if (lastStoryIndex[key] !== null && options.length > 1) {
    while (index === lastStoryIndex[key]) {
      index = Math.floor(Math.random() * options.length);
    }
  }
  lastStoryIndex[key] = index;
  storyHeading.textContent = `You have given water to ${bucketTitles[key] || key}`;
  storyBody.textContent = options[index];
  storyArea.classList.add('visible');
  if (storyTimeout) {
    clearTimeout(storyTimeout);
  }
  storyTimeout = setTimeout(() => {
    storyArea.classList.remove('visible');
  }, STORY_DURATION);
}

async function fetchData() {
  if (!testMode) {
    const response = await fetch("http://localhost:5000/data");
    const data = await response.json();
    for (let key in data) {
      updateBar(key, data[key]);
    }
  }
}

setInterval(fetchData, 1000);
