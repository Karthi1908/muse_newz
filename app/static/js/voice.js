// Voice Topic Recording & Muse Voice Transcribe Client (FR-002, Story 8)
window.DailyMuseVoice = {
  mediaRecorder: null,
  chunks: [],
  recording: false,

  toggleRecord: async function () {
    const btn = document.getElementById("btn-voice-record");
    const statusEl = document.getElementById("voice-status-msg");
    if (this.recording && this.mediaRecorder) {
      this.mediaRecorder.stop();
      this.recording = false;
      btn.textContent = "🎙️ Speak Topic Change";
      return;
    }

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      statusEl.textContent = "Microphone access unavailable in this browser. Please type your topic change.";
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      this.chunks = [];
      this.mediaRecorder = new MediaRecorder(stream);
      this.mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) this.chunks.push(e.data);
      };
      this.mediaRecorder.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(this.chunks, { type: "audio/webm" });
        await this.uploadVoiceCommand(blob);
      };
      this.mediaRecorder.start();
      this.recording = true;
      btn.textContent = "⏹️ Stop Recording";
      statusEl.textContent = "Listening... (e.g. 'drop space launch, add climate tech')";
      setTimeout(() => {
        if (this.recording && this.mediaRecorder) {
          this.mediaRecorder.stop();
          this.recording = false;
          btn.textContent = "🎙️ Speak Topic Change";
        }
      }, 28000);
    } catch (err) {
      statusEl.textContent = `Microphone error (${err.message}). Please type your change below.`;
    }
  },

  uploadVoiceCommand: async function (blob) {
    const statusEl = document.getElementById("voice-status-msg");
    statusEl.textContent = "Transcribing speech with Meta Muse Voice Transcribe...";
    const formData = new FormData();
    formData.append("audio", blob, "topic_command.webm");
    const hintInput = document.getElementById("topic-command-input")?.value || "";
    formData.append("fallback_hint", hintInput);

    try {
      const resp = await fetch("/api/topics/voice", { method: "POST", body: formData });
      const data = await resp.json();
      statusEl.textContent = data.stt_message || data.assistant_message || "";
      if (data.proposal) {
        window.DailyMuseApp.renderTopicProposal(data.proposal);
      }
    } catch (err) {
      statusEl.textContent = "Voice request failed; please retry or type your topic change.";
    }
  },
};
