"""
Mission 2: Wave or Particle? - Double-Slit Experiment.
Calculates classical wave intensity, quantum probability amplitudes,
and decoherence under which-path measurement.
"""

from dataclasses import dataclass
from typing import Dict, Any, List
import math
import numpy as np

from app.physics.constants import HBAR, ELECTRON_MASS, PLANCK_H, NM_TO_METER, meters_to_nm


@dataclass
class DoubleSlitResult:
    wavelength_nm: float
    slit_separation_um: float
    slit_width_um: float
    screen_distance_m: float
    which_path_enabled: bool
    num_slits: int  # 1 or 2

    # Screen coordinates in mm
    screen_positions_mm: List[float]
    classical_intensity: List[float]
    quantum_probability: List[float]
    fringes_peak_count: int
    visibility: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "wavelength_nm": round(self.wavelength_nm, 3),
            "slit_separation_um": round(self.slit_separation_um, 3),
            "slit_width_um": round(self.slit_width_um, 3),
            "screen_distance_m": round(self.screen_distance_m, 3),
            "which_path_enabled": self.which_path_enabled,
            "num_slits": self.num_slits,
            "screen_positions_mm": [round(y, 3) for y in self.screen_positions_mm],
            "classical_intensity": [round(float(v), 5) for v in self.classical_intensity],
            "quantum_probability": [round(float(v), 5) for v in self.quantum_probability],
            "fringes_peak_count": self.fringes_peak_count,
            "visibility": round(self.visibility, 4),
        }


def calculate_double_slit(
    wavelength_nm: float = 0.5,       # de Broglie wavelength or photon wavelength in nm
    slit_separation_um: float = 2.0,  # separation d in micrometers
    slit_width_um: float = 0.4,       # width w of each slit in micrometers
    screen_distance_m: float = 1.0,   # distance L to screen in meters
    which_path_enabled: bool = False, # measurement interaction destroying coherence
    num_slits: int = 2,               # 1 or 2 slits open
    num_points: int = 300,
    screen_span_mm: float = 5.0,      # screen range [-span, +span]
) -> DoubleSlitResult:
    """
    Computes Fraunhofer diffraction/interference pattern on a distant screen.
    Includes diffraction envelope: sinc^2(beta) where beta = pi * w * sin(theta) / lambda
    and interference factor:
      - Two slits, no detector: cos^2(alpha) where alpha = pi * d * sin(theta) / lambda
      - Two slits with which-path detector: loss of cross term (incoherent sum of single slits)
      - Single slit: single slit diffraction only
    """
    lam_m = wavelength_nm * 1e-9
    d_m = slit_separation_um * 1e-6
    w_m = slit_width_um * 1e-6
    L_m = screen_distance_m

    y_mm = np.linspace(-screen_span_mm, screen_span_mm, num_points)
    y_m = y_mm * 1e-3

    # Small angle approximation: theta ~ y / L
    theta = y_m / L_m

    # Diffraction envelope parameter: beta = pi * w * sin(theta) / lambda
    beta = (np.pi * w_m * theta) / lam_m
    # sinc(0) = 1
    diffraction = np.sinc(beta / np.pi) ** 2  # np.sinc(x) is sin(pi*x)/(pi*x)

    # Interference parameter: alpha = pi * d * sin(theta) / lambda
    alpha = (np.pi * d_m * theta) / lam_m

    if num_slits == 1:
        # Single slit at center
        classical_I = diffraction
        quantum_P = diffraction.copy()
        visibility = 0.0
    else:
        # Classical wave interference
        classical_I = diffraction * (np.cos(alpha) ** 2)

        if which_path_enabled:
            # Quantum measurement decoherence: which-path information destroys phase coherence!
            # The density matrix off-diagonal elements vanish (decoherence).
            # Resulting pattern is the incoherent sum of probabilities from slit 1 and slit 2.
            # Shift single-slit envelopes by +/- d/2
            theta_1 = (y_m - d_m / 2.0) / L_m
            theta_2 = (y_m + d_m / 2.0) / L_m
            beta_1 = (np.pi * w_m * theta_1) / lam_m
            beta_2 = (np.pi * w_m * theta_2) / lam_m
            p_slit1 = np.sinc(beta_1 / np.pi) ** 2
            p_slit2 = np.sinc(beta_2 / np.pi) ** 2
            quantum_P = 0.5 * (p_slit1 + p_slit2)
            visibility = 0.0
        else:
            # Fully coherent quantum interference:
            # P(y) = |psi_1 + psi_2|^2 = |psi_1|^2 + |psi_2|^2 + 2 Re(psi_1* psi_2)
            quantum_P = diffraction * (np.cos(alpha) ** 2)
            # Visibility V = (I_max - I_min) / (I_max + I_min) near center
            visibility = 1.0

    # Normalize patterns so maximum is 1.0 for visual plotting
    max_c = np.max(classical_I) if np.max(classical_I) > 0 else 1.0
    classical_I = classical_I / max_c

    max_q = np.max(quantum_P) if np.max(quantum_P) > 0 else 1.0
    quantum_P = quantum_P / max_q

    # Count peaks in the quantum pattern
    peaks = 0
    for i in range(1, len(quantum_P) - 1):
        if quantum_P[i] > quantum_P[i - 1] and quantum_P[i] > quantum_P[i + 1] and quantum_P[i] > 0.05:
            peaks += 1

    return DoubleSlitResult(
        wavelength_nm=wavelength_nm,
        slit_separation_um=slit_separation_um,
        slit_width_um=slit_width_um,
        screen_distance_m=screen_distance_m,
        which_path_enabled=which_path_enabled,
        num_slits=num_slits,
        screen_positions_mm=y_mm.tolist(),
        classical_intensity=classical_I.tolist(),
        quantum_probability=quantum_P.tolist(),
        fringes_peak_count=peaks,
        visibility=visibility,
    )
