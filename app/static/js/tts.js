// Client-Side Browser SpeechSynthesis TTS Service (Constitution §2: Meta has no TTS)
window.DailyMuseTTS = {
  speaking: false,
  speakArticle: function (elementId) {
    if (!("speechSynthesis" in window)) {
      alert("Browser SpeechSynthesis is not supported in this browser.");
      return;
    }
    if (window.speechSynthesis.speaking) {
      window.speechSynthesis.cancel();
      this.speaking = false;
      return;
    }
    const el = document.getElementById(elementId);
    if (!el) return;
    const headline = el.querySelector(".article-headline")?.innerText || "";
    const deck = el.querySelector(".article-deck")?.innerText || "";
    const body = el.querySelector(".article-body")?.innerText || "";
    const utterance = new SpeechSynthesisUtterance(`${headline}. ${deck}. ${body}`);
    utterance.rate = 1.02;
    utterance.onend = () => {
      this.speaking = false;
    };
    this.speaking = true;
    window.speechSynthesis.speak(utterance);
  },
  stopAll: function () {
    if ("speechSynthesis" in window) {
      window.speechSynthesis.cancel();
      this.speaking = false;
    }
  },
};
