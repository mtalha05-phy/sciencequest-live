/**
 * ScienceQuest Live - Master Frontend Controller
 * Coordinates UI navigation, WebSockets synchronization, canvas engines,
 * audience voting, Quark AI companion, and Twitch live stream chat.
 */

class ScienceQuestApp {
  constructor() {
    this.ws = null;
    this.state = null;
    this.currentView = 'home';
    this.username = localStorage.getItem('sq_username') || `Viewer_${Math.floor(1000 + Math.random() * 9000)}`;
    localStorage.setItem('sq_username', this.username);

    // Canvas Visualizers
    this.activeVisualizer = null;
    this.quarkMascot = null;
    this.lastFrameTime = performance.now();

    this.initElements();
    this.initEventListeners();
    this.initQuarkMascot();
    this.initVisualizer();
    this.updateProfileUI();
    this.connectWebSocket();
    this.startMainRenderLoop();
  }

  initElements() {
    this.dom = {
      navTabs: document.querySelectorAll('.nav-tab-btn'),
      viewSections: document.querySelectorAll('.view-section'),
      canvas: document.getElementById('science-canvas'),
      hudMissionTitle: document.getElementById('hud-mission-title'),
      hudMissionTopic: document.getElementById('hud-mission-topic'),
      slidersContainer: document.getElementById('sliders-container'),
      votingQuestion: document.getElementById('voting-question'),
      votingOptions: document.getElementById('voting-options'),
      votingTimer: document.getElementById('voting-timer'),
      votingRoundBadge: document.getElementById('voting-round-badge'),
      compClassicalVal: document.getElementById('comp-classical-val'),
      compClassicalNote: document.getElementById('comp-classical-note'),
      compQuantumVal: document.getElementById('comp-quantum-val'),
      compQuantumNote: document.getElementById('comp-quantum-note'),
      quarkBubble: document.getElementById('quark-bubble-text'),
      quarkInput: document.getElementById('quark-input'),
      quarkSendBtn: document.getElementById('quark-send-btn'),
      tierBtns: document.querySelectorAll('.tier-btn'),
      chatMessagesBox: document.getElementById('chat-messages-box'),
      chatInput: document.getElementById('chat-input'),
      chatSendBtn: document.getElementById('chat-send-btn'),
      leaderboardModal: document.getElementById('leaderboard-modal'),
      leaderboardList: document.getElementById('leaderboard-list'),
      badgesGrid: document.getElementById('badges-grid'),
      hudEnergy: document.getElementById('hud-energy'),
      hudBarrier: document.getElementById('hud-barrier'),
      hudTransmission: document.getElementById('hud-transmission'),
    };
  }

  initEventListeners() {
    // Nav tabs
    this.dom.navTabs.forEach(btn => {
      btn.addEventListener('click', () => {
        const view = btn.dataset.view;
        this.switchView(view);
      });
    });

    // Tier buttons
    this.dom.tierBtns.forEach(btn => {
      btn.addEventListener('click', () => {
        const tier = btn.dataset.tier;
        this.setQuarkTier(tier);
      });
    });

    // Quark input
    this.dom.quarkSendBtn.addEventListener('click', () => this.sendQuarkQuestion());
    this.dom.quarkInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') this.sendQuarkQuestion();
    });

    // Chat input
    this.dom.chatSendBtn.addEventListener('click', () => this.sendChatMessage());
    this.dom.chatInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') this.sendChatMessage();
    });

    // Modal controls
    document.getElementById('btn-open-leaderboard')?.addEventListener('click', () => this.openLeaderboard());
    document.getElementById('btn-close-modal')?.addEventListener('click', () => {
      this.dom.leaderboardModal.classList.remove('open');
    });

    // Window resize
    window.addEventListener('resize', () => {
      if (this.dom.canvas) {
        this.resizeCanvas();
      }
    });
  }

  resizeCanvas() {
    const rect = this.dom.canvas.parentElement.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    this.dom.canvas.width = rect.width * dpr;
    this.dom.canvas.height = rect.height * dpr;
    const ctx = this.dom.canvas.getContext('2d');
    ctx.scale(dpr, dpr);
  }

  initQuarkMascot() {
    this.quarkMascot = new QuarkRenderer('quark-mascot-canvas');
  }

  initVisualizer() {
    if (!this.dom.canvas) return;
    this.resizeCanvas();
    this.activeVisualizer = new TunnelingVisualizer(this.dom.canvas);
  }

  switchView(viewName) {
    this.currentView = viewName;
    this.dom.navTabs.forEach(t => {
      t.classList.toggle('active', t.dataset.view === viewName);
    });
    this.dom.viewSections.forEach(s => {
      s.classList.toggle('active-view', s.id === `view-${viewName}`);
    });

    if (viewName === 'lab' || viewName === 'reality-battle') {
      setTimeout(() => this.resizeCanvas(), 50);
    }
  }

  connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws`;

    this.ws = new WebSocket(wsUrl);

    this.ws.onopen = () => {
      console.log('Connected to ScienceQuest Live WebSocket Hub');
    };

    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        this.handleWebSocketMessage(data);
      } catch (e) {
        console.error('Error parsing WS message:', e);
      }
    };

    this.ws.onclose = () => {
      console.log('WebSocket disconnected. Reconnecting in 3s...');
      setTimeout(() => this.connectWebSocket(), 3000);
    };
  }

  handleWebSocketMessage(data) {
    const event = data.event;

    if (event === 'init_state' || event === 'state_update') {
      this.state = data.state;
      this.renderFullState();
    } else if (event === 'vote_update' || event === 'voting_started') {
      if (this.state) this.state.voting_status = data.voting_status;
      this.renderVotingStatus(data.voting_status);
    } else if (event === 'quark_speech') {
      this.displayQuarkSpeech(data.answer, data.username, data.question);
    } else if (event === 'chat_message') {
      this.appendChatMessage(data.username, data.text, data.is_simulated);
    } else if (event === 'round_resolved') {
      this.handleRoundResolved(data.round_result, data.quark_explanation);
    }
  }

  renderFullState() {
    if (!this.state) return;

    // Update Headers
    if (this.dom.hudMissionTitle) this.dom.hudMissionTitle.innerText = this.state.mission_title;
    if (this.dom.hudMissionTopic) this.dom.hudMissionTopic.innerText = this.state.mission_topic;

    // Switch Visualizer engine based on active mission
    const mid = this.state.active_mission_id;
    if (mid === 'mission_1' && !(this.activeVisualizer instanceof TunnelingVisualizer)) {
      this.activeVisualizer = new TunnelingVisualizer(this.dom.canvas);
    } else if (mid === 'mission_2' && !(this.activeVisualizer instanceof DoubleSlitVisualizer)) {
      this.activeVisualizer = new DoubleSlitVisualizer(this.dom.canvas);
    } else if (mid === 'mission_3' && !(this.activeVisualizer instanceof UncertaintyVisualizer)) {
      this.activeVisualizer = new UncertaintyVisualizer(this.dom.canvas);
    } else if (mid === 'mission_4' && !(this.activeVisualizer instanceof WaveLabVisualizer)) {
      this.activeVisualizer = new WaveLabVisualizer(this.dom.canvas);
    } else if (mid === 'mission_5' && !(this.activeVisualizer instanceof BoundaryVisualizer)) {
      this.activeVisualizer = new BoundaryVisualizer(this.dom.canvas);
    }

    if (this.activeVisualizer && this.state.physics_result) {
      this.activeVisualizer.setData(this.state.physics_result);
    }

    // Render HUD and Sliders
    this.renderHUDStats();
    this.renderParameterSliders();
    this.renderComparisonBox();
    this.renderVotingStatus(this.state.voting_status);
  }

  renderHUDStats() {
    const p = this.state.physics_result;
    if (!p) return;

    if (this.state.active_mission_id === 'mission_1') {
      if (this.dom.hudEnergy) this.dom.hudEnergy.innerText = `${p.energy_ev} eV`;
      if (this.dom.hudBarrier) this.dom.hudBarrier.innerText = `${p.barrier_height_ev} eV`;
      if (this.dom.hudTransmission) this.dom.hudTransmission.innerText = `${(p.quantum_transmission * 100).toFixed(2)}% (Quantum)`;
    } else if (this.state.active_mission_id === 'mission_2') {
      if (this.dom.hudEnergy) this.dom.hudEnergy.innerText = `λ = ${p.wavelength_nm} nm`;
      if (this.dom.hudBarrier) this.dom.hudBarrier.innerText = `d = ${p.slit_separation_um} µm`;
      if (this.dom.hudTransmission) this.dom.hudTransmission.innerText = p.which_path_enabled ? 'Which-Path ON' : 'Coherent Fringes';
    } else if (this.state.active_mission_id === 'mission_3') {
      if (this.dom.hudEnergy) this.dom.hudEnergy.innerText = `Δx = ${p.delta_x_nm} nm`;
      if (this.dom.hudBarrier) this.dom.hudBarrier.innerText = `Δp = ${p.delta_p_si}`;
      if (this.dom.hudTransmission) this.dom.hudTransmission.innerText = `Product: ${p.ratio_to_minimum}× (ℏ/2)`;
    }
  }

  renderParameterSliders() {
    const container = this.dom.slidersContainer;
    if (!container) return;
    container.innerHTML = '';

    const allowed = this.state.allowed_ranges || {};
    const curr = this.state.current_params || {};

    for (const [key, conf] of Object.entries(allowed)) {
      const val = curr[key] !== undefined ? curr[key] : conf.min;
      const cleanName = key.replace(/_/g, ' ').toUpperCase();

      const unit = document.createElement('div');
      unit.className = 'slider-unit';

      unit.innerHTML = `
        <div class="slider-label-row">
          <span class="slider-name">${cleanName}</span>
          <span class="slider-value" id="val-${key}">${val} ${conf.unit || ''}</span>
        </div>
        <input type="range" 
               min="${conf.min}" 
               max="${conf.max}" 
               step="${conf.step}" 
               value="${val}" 
               id="slider-${key}">
      `;

      const sliderInput = unit.querySelector(`#slider-${key}`);
      sliderInput.addEventListener('input', (e) => {
        const numVal = parseFloat(e.target.value);
        document.getElementById(`val-${key}`).innerText = `${numVal} ${conf.unit || ''}`;
        this.updateParamDebounced(key, numVal);
      });

      container.appendChild(unit);
    }
  }

  updateParamDebounced(param, value) {
    clearTimeout(this._paramTimeout);
    this._paramTimeout = setTimeout(() => {
      fetch('/api/parameter', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ param, value }),
      });
    }, 120);
  }

  renderComparisonBox() {
    const p = this.state.physics_result;
    if (!p) return;

    if (this.state.active_mission_id === 'mission_1') {
      if (this.dom.compClassicalVal) {
        this.dom.compClassicalVal.innerText = `${(p.classical_transmission * 100).toFixed(0)}%`;
        this.dom.compClassicalVal.style.color = p.classical_crosses ? '#10b981' : '#ef4444';
      }
      if (this.dom.compClassicalNote) this.dom.compClassicalNote.innerText = p.classical_note;

      if (this.dom.compQuantumVal) {
        this.dom.compQuantumVal.innerText = `${(p.quantum_transmission * 100).toFixed(2)}%`;
        this.dom.compQuantumVal.style.color = '#c084fc';
      }
      if (this.dom.compQuantumNote) {
        this.dom.compQuantumNote.innerText = (
          `Tunneling decay constant κ = ${p.kappa_or_k2_inv_nm || 0} nm⁻¹. ` +
          `de Broglie wavelength λ = ${p.de_broglie_wavelength_nm || 0} nm.`
        );
      }
    }
  }

  renderVotingStatus(vStatus) {
    if (!vStatus) return;

    if (this.dom.votingQuestion) this.dom.votingQuestion.innerText = vStatus.question;
    if (this.dom.votingTimer) {
      this.dom.votingTimer.innerText = vStatus.voting_open ? `${vStatus.time_remaining_seconds}s REMAINING` : 'ROUND CLOSED';
      this.dom.votingTimer.style.background = vStatus.voting_open ? 'rgba(239, 68, 68, 0.15)' : 'rgba(100, 116, 139, 0.2)';
    }

    const optionsContainer = this.dom.votingOptions;
    if (!optionsContainer) return;
    optionsContainer.innerHTML = '';

    const options = vStatus.options || {};
    const tallies = vStatus.tallies || {};
    const pcts = vStatus.percentages || {};

    for (const [letter, text] of Object.entries(options)) {
      const pct = pcts[letter] || 0;
      const count = tallies[letter] || 0;

      const optBtn = document.createElement('button');
      optBtn.className = 'vote-opt-btn';
      optBtn.innerHTML = `
        <div class="vote-bar-fill" style="width: ${pct}%"></div>
        <div class="vote-content">
          <div><span class="vote-opt-letter">[${letter}]</span> ${text}</div>
          <span class="vote-percent">${pct}% (${count})</span>
        </div>
      `;

      optBtn.addEventListener('click', () => {
        this.castVote(letter);
      });

      optionsContainer.appendChild(optBtn);
    }
  }

  castVote(optionLetter) {
    fetch('/api/voting/vote', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: this.username, option: optionLetter }),
    }).then(res => {
      if (res.ok) {
        this.appendChatMessage(this.username, `!vote ${optionLetter}`, false);
        if (this.quarkMascot) this.quarkMascot.setMood('happy');
      }
    });
  }

  setQuarkTier(tier) {
    this.dom.tierBtns.forEach(b => b.classList.toggle('active', b.dataset.tier === tier));
    fetch('/api/quark/level', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ level: tier }),
    });
  }

  displayQuarkSpeech(text, user, question) {
    if (this.dom.quarkBubble) {
      this.dom.quarkBubble.innerText = text;
    }
    if (this.quarkMascot) {
      this.quarkMascot.setMood('calculating');
      setTimeout(() => this.quarkMascot.setMood('curious'), 1800);
    }
  }

  sendQuarkQuestion() {
    const q = this.dom.quarkInput.value.trim();
    if (!q) return;
    this.dom.quarkInput.value = '';

    this.displayQuarkSpeech('Processing question with quantum physics engine...', 'Quark', q);
    if (this.quarkMascot) this.quarkMascot.setMood('calculating');

    fetch('/api/quark/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question: q, username: this.username }),
    });
  }

  sendChatMessage() {
    const text = this.dom.chatInput.value.trim();
    if (!text) return;
    this.dom.chatInput.value = '';

    fetch('/api/chat/send', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: this.username, text }),
    });
  }

  appendChatMessage(user, text, isSimulated) {
    const box = this.dom.chatMessagesBox;
    if (!box) return;

    const msg = document.createElement('div');
    msg.className = 'chat-msg';

    const tag = isSimulated
      ? '<span class="chat-tag sim">[SIM]</span>'
      : '<span class="chat-tag live">[TWITCH]</span>';

    msg.innerHTML = `${tag}<span class="chat-user">${user}:</span> ${text}`;
    box.appendChild(msg);
    box.scrollTop = box.scrollHeight;
  }

  handleRoundResolved(roundResult, explanation) {
    if (this.quarkMascot) this.quarkMascot.setMood('happy');
    this.displayQuarkSpeech(explanation, 'Quark', 'Round Results');
  }

  openLeaderboard() {
    fetch('/api/leaderboard')
      .then(r => r.json())
      .then(data => {
        const list = this.dom.leaderboardList;
        list.innerHTML = '';
        (data.leaderboard || []).forEach((player, idx) => {
          const item = document.createElement('div');
          item.className = 'hud-row';
          item.style.padding = '0.5rem 0';
          item.style.borderBottom = '1px solid rgba(255,255,255,0.06)';
          item.innerHTML = `
            <span>#${idx + 1} <strong>${player.username}</strong></span>
            <span style="color: #06b6d4; font-weight: 700;">${player.points} pts</span>
          `;
          list.appendChild(item);
        });
        this.dom.leaderboardModal.classList.add('open');
      });
  }

  openProfileModal() {
    const modal = document.getElementById('profile-modal');
    if (!modal) return;
    const input = document.getElementById('profile-username-input');
    if (input) input.value = this.username;

    fetch('/api/leaderboard')
      .then(r => r.json())
      .then(data => {
        const leaders = data.leaderboard || [];
        const me = leaders.find(p => p.username.toLowerCase() === this.username.toLowerCase()) || {
          points: 0, current_streak: 0, accuracy_pct: 0, badges: []
        };
        const modalRank = document.getElementById('modal-rank');
        const modalPoints = document.getElementById('modal-points');
        const modalStreak = document.getElementById('modal-streak');
        const modalAcc = document.getElementById('modal-accuracy');
        const badgesList = document.getElementById('modal-badges-list');

        if (modalPoints) modalPoints.innerText = `${me.points} pts`;
        if (modalStreak) modalStreak.innerText = `${me.current_streak}🔥`;
        if (modalAcc) modalAcc.innerText = `${me.accuracy_pct}%`;
        if (modalRank) {
          if (me.points >= 500) modalRank.innerText = 'Principal Quantum Investigator';
          else if (me.points >= 200) modalRank.innerText = 'Senior Research Fellow';
          else if (me.points >= 100) modalRank.innerText = 'Staff Physicist';
          else modalRank.innerText = 'Junior Investigator';
        }

        if (badgesList) {
          badgesList.innerHTML = '';
          const earned = me.badges || [];
          if (earned.length === 0) {
            badgesList.innerHTML = '<span style="color:var(--text-dim); font-size:0.8rem;">No badges earned yet. Complete experiments to unlock badges!</span>';
          } else {
            earned.forEach(bId => {
              const bInfo = (data.badges || {})[bId] || { name: bId, icon: '⚡' };
              badgesList.innerHTML += `<div style="background:rgba(245,158,11,0.15); color:var(--gold-accent); border:1px solid rgba(245,158,11,0.3); padding:0.3rem 0.6rem; border-radius:4px; font-size:0.78rem; font-weight:600;">${bInfo.icon} ${bInfo.name}</div>`;
            });
          }
        }
        modal.classList.add('open');
      });
  }

  saveProfileName() {
    const input = document.getElementById('profile-username-input');
    if (!input) return;
    const clean = input.value.trim();
    if (!clean) return;
    this.username = clean;
    localStorage.setItem('sq_username', this.username);
    this.updateProfileUI();
    document.getElementById('profile-modal')?.classList.remove('open');
  }

  updateProfileUI() {
    const navName = document.getElementById('nav-player-name');
    const homeName = document.getElementById('home-player-name');
    if (navName) navName.innerText = this.username;
    if (homeName) homeName.innerText = this.username;

    fetch('/api/leaderboard')
      .then(r => r.json())
      .then(data => {
        const leaders = data.leaderboard || [];
        const me = leaders.find(p => p.username.toLowerCase() === this.username.toLowerCase()) || {
          points: 0, current_streak: 0, accuracy_pct: 0, badges: []
        };
        const navPts = document.getElementById('nav-player-points');
        const homePts = document.getElementById('home-player-pts');
        const homeStreak = document.getElementById('home-player-streak');
        const homeAcc = document.getElementById('home-player-acc');
        const homeRank = document.getElementById('home-player-rank');
        const homeBadges = document.getElementById('home-player-badges');
        const homeLeaders = document.getElementById('home-scoreboard-leaders');

        if (navPts) navPts.innerText = `${me.points} pts`;
        if (homePts) homePts.innerText = `${me.points}`;
        if (homeStreak) homeStreak.innerText = `${me.current_streak}🔥`;
        if (homeAcc) homeAcc.innerText = `${me.accuracy_pct}%`;
        if (homeRank) {
          if (me.points >= 500) homeRank.innerText = 'Principal Quantum Investigator';
          else if (me.points >= 200) homeRank.innerText = 'Senior Research Fellow';
          else if (me.points >= 100) homeRank.innerText = 'Staff Physicist';
          else homeRank.innerText = 'Junior Investigator';
        }
        if (homeBadges) {
          const earned = me.badges || [];
          let badgeStr = earned.length > 0 ? '' : '⚡ 🔒 🔒 🔒 🔒';
          earned.forEach(b => { badgeStr += '🏅 '; });
          homeBadges.innerText = badgeStr;
        }

        if (homeLeaders) {
          homeLeaders.innerHTML = '';
          leaders.slice(0, 5).forEach((p, i) => {
            homeLeaders.innerHTML += `
              <div style="display:flex; justify-content:space-between; padding:0.4rem 0; border-bottom:1px solid rgba(255,255,255,0.05); font-size:0.85rem;">
                <span>#${i + 1} <strong>${p.username}</strong></span>
                <span style="color:var(--cyan-accent); font-family:var(--font-mono); font-weight:700;">${p.points} pts (${p.current_streak}🔥)</span>
              </div>
            `;
          });
        }
      });
  }

  startMainRenderLoop() {
    const loop = (now) => {
      const dt = Math.min(0.1, (now - this.lastFrameTime) / 1000);
      this.lastFrameTime = now;

      if (this.activeVisualizer && (this.currentView === 'lab' || this.currentView === 'reality-battle')) {
        this.activeVisualizer.update(dt);
        this.activeVisualizer.render();
      }

      requestAnimationFrame(loop);
    };
    requestAnimationFrame(loop);
  }
}

window.addEventListener('DOMContentLoaded', () => {
  window.app = new ScienceQuestApp();
});
