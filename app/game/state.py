"""
Game state manager for ScienceQuest Live.
Coordinates missions, experimental parameters, live voting rounds, and synchronized viewer state.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
import time

from app.physics.tunneling import calculate_tunneling
from app.physics.double_slit import calculate_double_slit
from app.physics.uncertainty import calculate_uncertainty
from app.physics.wave_lab import calculate_wave_lab
from app.physics.correspondence import calculate_correspondence


MISSION_DEFINITIONS = {
    "mission_1": {
        "id": "mission_1",
        "title": "The Impossible Wall",
        "world": "quantum",
        "badge_id": "badge_quantum_explorer",
        "badge_name": "Quantum Explorer",
        "difficulty": "Beginner to Intermediate",
        "topic": "Classical Mechanics vs Quantum Tunneling",
        "description": "Investigate why a quantum particle can tunnel through an insurmountable energy barrier where classical physics forbids transmission.",
        "default_params": {
            "energy_ev": 3.5,
            "barrier_height_ev": 5.0,
            "barrier_width_nm": 0.45,
            "particle_mass_me": 1.0,
        },
        "allowed_ranges": {
            "energy_ev": {"min": 0.5, "max": 10.0, "step": 0.1, "unit": "eV"},
            "barrier_height_ev": {"min": 1.0, "max": 12.0, "step": 0.1, "unit": "eV"},
            "barrier_width_nm": {"min": 0.1, "max": 2.0, "step": 0.05, "unit": "nm"},
            "particle_mass_me": {"min": 0.5, "max": 5.0, "step": 0.5, "unit": "m_e"},
        },
        "default_question": {
            "text": "An electron with 3.5 eV approaches a 5.0 eV barrier. Can it reach the other side?",
            "options": {
                "A": "Yes! Non-zero probability via quantum tunneling",
                "B": "No, forbidden in both classical and quantum physics",
                "C": "Yes, classical physics predicts it passes easily",
                "D": "Only if we wait for thermal heat fluctuations",
            },
            "correct_option": "A",
            "scientific_rationale": "In classical mechanics, kinetic energy K = E - V0 < 0 is forbidden. But the quantum wavefunction decays exponentially inside the barrier, leaving a non-zero amplitude on the other side!",
        },
    },
    "mission_2": {
        "id": "mission_2",
        "title": "Wave or Particle?",
        "world": "quantum",
        "badge_id": "badge_wave_detective",
        "badge_name": "Wave Detective",
        "difficulty": "Intermediate",
        "topic": "Wave-Particle Duality & Which-Path Decoherence",
        "description": "Send particles through two slits and test how placing a detector at the slits destroys the interference pattern through quantum decoherence.",
        "default_params": {
            "wavelength_nm": 0.5,
            "slit_separation_um": 2.5,
            "slit_width_um": 0.5,
            "screen_distance_m": 1.2,
            "which_path_enabled": False,
            "num_slits": 2,
        },
        "allowed_ranges": {
            "wavelength_nm": {"min": 0.1, "max": 2.0, "step": 0.05, "unit": "nm"},
            "slit_separation_um": {"min": 1.0, "max": 6.0, "step": 0.5, "unit": "µm"},
            "slit_width_um": {"min": 0.2, "max": 1.5, "step": 0.1, "unit": "µm"},
            "screen_distance_m": {"min": 0.5, "max": 3.0, "step": 0.1, "unit": "m"},
        },
        "default_question": {
            "text": "What happens to the interference pattern when we turn on a detector to record which slit each particle passes through?",
            "options": {
                "A": "The interference fringes completely vanish into an incoherent blur",
                "B": "The fringes become twice as bright and sharp",
                "C": "The pattern flips upside down",
                "D": "Nothing changes; particles do not know they are watched",
            },
            "correct_option": "A",
            "scientific_rationale": "Which-path information destroys quantum phase coherence between the alternative trajectories, eliminating the cross-term in the probability distribution.",
        },
    },
    "mission_3": {
        "id": "mission_3",
        "title": "The Uncertainty Challenge",
        "world": "quantum",
        "badge_id": "badge_quantum_thinker",
        "badge_name": "Quantum Thinker",
        "difficulty": "Intermediate to Advanced",
        "topic": "Heisenberg's Uncertainty Principle",
        "description": "Squeeze the spatial width of a quantum wavepacket and watch its momentum distribution broaden to satisfy Δx · Δp ≥ ℏ/2.",
        "default_params": {
            "sigma_x_nm": 0.25,
            "central_energy_ev": 5.0,
            "packet_chirp": 0.0,
        },
        "allowed_ranges": {
            "sigma_x_nm": {"min": 0.05, "max": 1.5, "step": 0.05, "unit": "nm"},
            "central_energy_ev": {"min": 1.0, "max": 20.0, "step": 0.5, "unit": "eV"},
            "packet_chirp": {"min": 0.0, "max": 3.0, "step": 0.1, "unit": ""},
        },
        "default_question": {
            "text": "If we trap an electron into an extremely narrow spatial pinhole (reducing Δx by 10x), what happens to its momentum uncertainty Δp?",
            "options": {
                "A": "Δp increases by at least 10x (momentum spreads out)",
                "B": "Δp decreases by 10x (it comes to a dead stop)",
                "C": "Δp stays exactly zero",
                "D": "It depends entirely on the quality of our sensors",
            },
            "correct_option": "A",
            "scientific_rationale": "Heisenberg's uncertainty relation Δx · Δp ≥ ℏ/2 is an intrinsic mathematical property of wave mechanics and Fourier conjugate variables, not instrument error.",
        },
    },
    "mission_4": {
        "id": "mission_4",
        "title": "The Wave Laboratory",
        "world": "classical",
        "badge_id": "badge_wave_master",
        "badge_name": "Wave Master",
        "difficulty": "Beginner to Intermediate",
        "topic": "Superposition & Classical vs Quantum Waves",
        "description": "Combine classical waves with varying phases and compare with quantum probability amplitude interference.",
        "default_params": {
            "wavelength_m": 1.0,
            "amplitude_1": 1.0,
            "amplitude_2": 1.0,
            "phase_diff_deg": 180.0,
            "frequency_hz": 1.0,
        },
        "allowed_ranges": {
            "wavelength_m": {"min": 0.2, "max": 3.0, "step": 0.1, "unit": "m"},
            "amplitude_1": {"min": 0.0, "max": 2.0, "step": 0.1, "unit": "a.u."},
            "amplitude_2": {"min": 0.0, "max": 2.0, "step": 0.1, "unit": "a.u."},
            "phase_diff_deg": {"min": 0.0, "max": 360.0, "step": 15.0, "unit": "deg"},
        },
        "default_question": {
            "text": "When two equal classical waves meet with a phase difference of 180 degrees (π radians), what is the resultant amplitude?",
            "options": {
                "A": "Zero (Complete destructive cancellation)",
                "B": "Twice the amplitude (Constructive amplification)",
                "C": "Half of the original amplitude",
                "D": "The waves bounce off each other elastically",
            },
            "correct_option": "A",
            "scientific_rationale": "At 180 degrees out of phase, cos(180) = -1, leading to complete destructive interference: resultant amplitude = |A1 - A2| = 0.",
        },
    },
    "mission_5": {
        "id": "mission_5",
        "title": "The Classical–Quantum Boundary",
        "world": "battle",
        "badge_id": "badge_reality_explorer",
        "badge_name": "Reality Explorer",
        "difficulty": "Advanced",
        "topic": "The Correspondence Principle & Wavepacket Spreading",
        "description": "Observe why a macroscopic baseball follows a definite Newtonian trajectory while an electron's wavepacket disperses instantaneously.",
        "default_params": {
            "object_preset": "electron",
            "initial_velocity_mps": 10.0,
            "time_elapsed_s": 1e-14,
        },
        "allowed_ranges": {
            "initial_velocity_mps": {"min": 1.0, "max": 100.0, "step": 1.0, "unit": "m/s"},
        },
        "default_question": {
            "text": "Why do macroscopic objects like baseballs never visibly exhibit wavepacket spreading or double-slit interference in daily life?",
            "options": {
                "A": "Their immense mass makes the dispersion timescale millions of years and de Broglie wavelength unobservably minute",
                "B": "Quantum mechanics shuts off when an object weighs more than 1 gram",
                "C": "Gravity cancels all quantum wavefunctions instantly",
                "D": "Macroscopic matter is made of different fundamental particles",
            },
            "correct_option": "A",
            "scientific_rationale": "By the Correspondence Principle, as mass increases, the action S >> ℏ, dispersion timescale tau = 2 m w0^2 / ℏ becomes astronomical, and environmental decoherence suppresses interference in picoseconds.",
        },
    },
}


class GameStateManager:
    """Manages full live experiment state, parameters, physics computations, and voting rounds."""

    def __init__(self):
        self.active_mission_id: str = "mission_1"
        self.active_world: str = "quantum"
        self.mission_params: Dict[str, Dict[str, Any]] = {
            m_id: dict(m_info["default_params"])
            for m_id, m_info in MISSION_DEFINITIONS.items()
        }
        self.active_physics_result: Dict[str, Any] = {}
        self.voting_open: bool = False
        self.voting_start_time: float = 0.0
        self.voting_duration_seconds: int = 45
        self.votes: Dict[str, str] = {}  # viewer_username -> option (e.g. "A")
        self.last_round_result: Optional[Dict[str, Any]] = None
        self.is_simulating: bool = False
        self.round_id: int = 1

        # Run initial physics calculation for default mission
        self.recalculate_current_physics()

    def get_mission_def(self, mission_id: Optional[str] = None) -> Dict[str, Any]:
        mid = mission_id or self.active_mission_id
        return MISSION_DEFINITIONS.get(mid, MISSION_DEFINITIONS["mission_1"])

    def set_active_mission(self, mission_id: str) -> bool:
        if mission_id not in MISSION_DEFINITIONS:
            return False
        self.active_mission_id = mission_id
        self.active_world = MISSION_DEFINITIONS[mission_id]["world"]
        self.voting_open = False
        self.votes.clear()
        self.round_id += 1
        self.recalculate_current_physics()
        return True

    def update_parameter(self, param_name: str, value: Any) -> bool:
        m_def = self.get_mission_def()
        if param_name not in m_def["allowed_ranges"] and param_name not in m_def["default_params"]:
            return False

        # Validate range if numeric
        ranges = m_def.get("allowed_ranges", {}).get(param_name)
        if ranges and isinstance(value, (int, float)):
            val = float(value)
            if val < ranges["min"] or val > ranges["max"]:
                return False
            self.mission_params[self.active_mission_id][param_name] = val
        else:
            self.mission_params[self.active_mission_id][param_name] = value

        self.recalculate_current_physics()
        return True

    def recalculate_current_physics(self) -> Dict[str, Any]:
        params = self.mission_params[self.active_mission_id]

        if self.active_mission_id == "mission_1":
            res = calculate_tunneling(
                energy_ev=params.get("energy_ev", 3.5),
                barrier_height_ev=params.get("barrier_height_ev", 5.0),
                barrier_width_nm=params.get("barrier_width_nm", 0.45),
                particle_mass_me=params.get("particle_mass_me", 1.0),
            )
            self.active_physics_result = res.to_dict()

        elif self.active_mission_id == "mission_2":
            res = calculate_double_slit(
                wavelength_nm=params.get("wavelength_nm", 0.5),
                slit_separation_um=params.get("slit_separation_um", 2.5),
                slit_width_um=params.get("slit_width_um", 0.5),
                screen_distance_m=params.get("screen_distance_m", 1.2),
                which_path_enabled=params.get("which_path_enabled", False),
                num_slits=params.get("num_slits", 2),
            )
            self.active_physics_result = res.to_dict()

        elif self.active_mission_id == "mission_3":
            res = calculate_uncertainty(
                sigma_x_nm=params.get("sigma_x_nm", 0.25),
                central_energy_ev=params.get("central_energy_ev", 5.0),
                packet_chirp=params.get("packet_chirp", 0.0),
            )
            self.active_physics_result = res.to_dict()

        elif self.active_mission_id == "mission_4":
            res = calculate_wave_lab(
                wavelength_m=params.get("wavelength_m", 1.0),
                amplitude_1=params.get("amplitude_1", 1.0),
                amplitude_2=params.get("amplitude_2", 1.0),
                phase_diff_deg=params.get("phase_diff_deg", 180.0),
                frequency_hz=params.get("frequency_hz", 1.0),
            )
            self.active_physics_result = res.to_dict()

        elif self.active_mission_id == "mission_5":
            res = calculate_correspondence(
                object_preset=params.get("object_preset", "electron"),
                initial_velocity_mps=params.get("initial_velocity_mps", 10.0),
                time_elapsed_s=params.get("time_elapsed_s", 1e-14),
            )
            self.active_physics_result = res.to_dict()

        return self.active_physics_result

    def start_voting_round(self, duration_seconds: int = 45) -> Dict[str, Any]:
        self.voting_open = True
        self.voting_start_time = time.time()
        self.voting_duration_seconds = duration_seconds
        self.votes.clear()
        self.round_id += 1
        return self.get_voting_status()

    def record_vote(self, username: str, option: str) -> bool:
        if not self.voting_open:
            return False
        clean_option = option.strip().upper()
        m_def = self.get_mission_def()
        valid_options = m_def["default_question"]["options"].keys()
        if clean_option not in valid_options:
            return False

        # One vote per user per round (duplicate vote overwrites or locks, here cleanly records)
        self.votes[username] = clean_option
        return True

    def get_voting_status(self) -> Dict[str, Any]:
        m_def = self.get_mission_def()
        q_info = m_def["default_question"]

        tallies = {opt: 0 for opt in q_info["options"].keys()}
        for opt in self.votes.values():
            if opt in tallies:
                tallies[opt] += 1

        total_votes = len(self.votes)
        percentages = {
            opt: (round((count / total_votes) * 100, 1) if total_votes > 0 else 0.0)
            for opt, count in tallies.items()
        }

        time_left = 0
        if self.voting_open:
            elapsed = time.time() - self.voting_start_time
            time_left = max(0, int(self.voting_duration_seconds - elapsed))
            if time_left == 0 and self.voting_open:
                # Automatically close when time expired
                self.voting_open = False

        return {
            "round_id": self.round_id,
            "voting_open": self.voting_open,
            "time_remaining_seconds": time_left,
            "total_votes": total_votes,
            "tallies": tallies,
            "percentages": percentages,
            "question": q_info["text"],
            "options": q_info["options"],
            "correct_option": q_info["correct_option"] if not self.voting_open else None,
        }

    def close_and_resolve_voting(self) -> Dict[str, Any]:
        self.voting_open = False
        m_def = self.get_mission_def()
        q_info = m_def["default_question"]
        correct_option = q_info["correct_option"]

        tallies = {opt: 0 for opt in q_info["options"].keys()}
        correct_voters: List[str] = []
        incorrect_voters: List[str] = []

        for user, opt in self.votes.items():
            if opt in tallies:
                tallies[opt] += 1
            if opt == correct_option:
                correct_voters.append(user)
            else:
                incorrect_voters.append(user)

        total_votes = len(self.votes)
        percentages = {
            opt: (round((count / total_votes) * 100, 1) if total_votes > 0 else 0.0)
            for opt, count in tallies.items()
        }

        # Determine community consensus (most voted option)
        consensus_opt = max(tallies.items(), key=lambda item: item[1])[0] if total_votes > 0 else None
        community_won = (consensus_opt == correct_option)

        result = {
            "round_id": self.round_id,
            "mission_id": self.active_mission_id,
            "total_votes": total_votes,
            "tallies": tallies,
            "percentages": percentages,
            "correct_option": correct_option,
            "consensus_option": consensus_opt,
            "community_won": community_won,
            "correct_voters": correct_voters,
            "incorrect_voters": incorrect_voters,
            "rationale": q_info["scientific_rationale"],
        }
        self.last_round_result = result
        return result

    def get_full_client_state(self) -> Dict[str, Any]:
        m_def = self.get_mission_def()
        return {
            "active_mission_id": self.active_mission_id,
            "active_world": self.active_world,
            "mission_title": m_def["title"],
            "mission_topic": m_def["topic"],
            "mission_description": m_def["description"],
            "allowed_ranges": m_def.get("allowed_ranges", {}),
            "current_params": self.mission_params[self.active_mission_id],
            "physics_result": self.active_physics_result,
            "voting_status": self.get_voting_status(),
            "last_round_result": self.last_round_result,
            "all_missions": [
                {
                    "id": m["id"],
                    "title": m["title"],
                    "world": m["world"],
                    "topic": m["topic"],
                    "badge_name": m["badge_name"],
                    "difficulty": m["difficulty"],
                }
                for m in MISSION_DEFINITIONS.values()
            ],
        }
