# ph_simulator_v4_viz.py
import pygame
import CoolProp.CoolProp as CP
import numpy as np
import math
import sys

# --- Constants ---
INITIAL_SCREEN_WIDTH = 1300
INITIAL_SCREEN_HEIGHT = 880
MIN_SCREEN_WIDTH = 950
MIN_SCREEN_HEIGHT = 700

# Colors (Defined with intent)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (255, 60, 60)        # Actual Compression / High Temp Line
BLUE = (100, 100, 255)     # Expansion / Liquid Line
GREEN = (60, 255, 60)      # Evaporation / Low Temp Vapor Line
GRAY = (120, 120, 120)     # Dome / Axes (Slightly darker)
PURPLE = (200, 0, 200)     # Ideal Compression Line
ORANGE = (255, 165, 0)     # Condensation Line
YELLOW = (255, 255, 0)     # Info Panel Titles / Legend Key
CYAN = (0, 255, 255)       # Highlight / Temp labels / Component Labels

# Refrigerant Choice
REFRIGERANT = 'R134a'

# --- Unit Conversion Factors ---
KPA_TO_PSIA = 0.1450377
PSIA_TO_PA = (1 / KPA_TO_PSIA) * 1000
PA_TO_PSIA = KPA_TO_PSIA / 1000
J_KG_TO_BTU_LB = 0.000430210
BTU_LB_TO_J_KG = 1 / J_KG_TO_BTU_LB
DELTA_K_TO_DELTA_F = 1.8
DELTA_F_TO_DELTA_K = 1 / DELTA_K_TO_DELTA_F
J_KGK_TO_BTU_LBR = 0.0002390057 # For entropy conversion if needed later

# --- Temperature Conversion ---
def kelvin_to_fahrenheit(T_k):
    return (T_k - 273.15) * 9/5 + 32 if T_k is not None else None
def fahrenheit_to_kelvin(T_f):
    return (T_f - 32) * 5/9 + 273.15 if T_f is not None else None

# --- UI Layout ---
INFO_PANEL_WIDTH = 340
PLOT_MARGIN_TOP = 60
PLOT_MARGIN_BOTTOM = 70
PLOT_MARGIN_LEFT = 95
PLOT_MARGIN_RIGHT = INFO_PANEL_WIDTH + 25
AXIS_LABEL_PADDING = 48
TICK_LABEL_PADDING = 5
COMPONENT_LABEL_OFFSET = 15


# --- V3 Base Simulation Class (Imperial Units) ---
class RefrigerationSimImperial:
    def __init__(self, screen_width, screen_height):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.fullscreen = False # Base class also needs this attribute

        # Fonts (Define base fonts here, Viz class can add more)
        try:
            pygame.font.init() # Ensure font module is initialized
        except Exception as e:
             print(f"Pygame font init error: {e}. Using default.")
             self.title_font = pygame.font.SysFont(None, 36)
             self.info_font = pygame.font.SysFont(None, 20)
             self.small_font = pygame.font.SysFont(None, 18)
             self.axis_font = pygame.font.SysFont(None, 20)
             self.tick_font = pygame.font.SysFont(None, 16)
        else:
             self.title_font = pygame.font.SysFont("Arial", 30)
             self.info_font = pygame.font.SysFont("Consolas", 15)
             self.small_font = pygame.font.SysFont("Consolas", 13)
             self.axis_font = pygame.font.SysFont("Arial", 16)
             self.tick_font = pygame.font.SysFont("Arial", 12)


        # Simulation Parameters (Default Values in IMPERIAL)
        self.reset_parameters()

        # Plotting Parameters (IMPERIAL Units)
        self.h_min_btu_lb = 40
        self.h_max_btu_lb = 210
        self.p_min_psia = 10
        self.p_max_psia = 400
        self.log_p_min = np.log10(self.p_min_psia)
        self.log_p_max = np.log10(self.p_max_psia)

        # Calculated State Points (Store main data in SI)
        self.state_points_si = {'1': {}, '2': {}, '2s': {}, '3': {}, '4': {}}
        self.performance = {'COP': None, 'Q_evap_btu_lb': None, 'W_comp_btu_lb': None, 'Q_cond_btu_lb': None}
        self.errors = []

        # Pre-calculate Dome & Update Layout
        self.dome_h_si = {'liq': [], 'vap': []}
        self.dome_p_pa = []
        self.update_layout()
        self.calculate_dome()
        self.calculate_cycle()

    def reset_parameters(self):
        """Resets simulation parameters to default IMPERIAL values."""
        self.p_evap_psia = 35.0   # Evaporating pressure (PSIA) -> ~30 F
        self.p_cond_psia = 160.0  # Condensing pressure (PSIA) -> ~115 F
        self.superheat_F = 10.0  # Superheat (°F difference)
        self.subcooling_F = 5.0   # Subcooling (°F difference)
        self.eta_comp = 0.75    # Isentropic compressor efficiency

    def update_layout(self):
        """Calculates plot area dimensions based on current screen size."""
        self.plot_x = PLOT_MARGIN_LEFT
        self.plot_y = PLOT_MARGIN_TOP
        self.plot_width = self.screen_width - PLOT_MARGIN_LEFT - PLOT_MARGIN_RIGHT
        self.plot_height = self.screen_height - PLOT_MARGIN_TOP - PLOT_MARGIN_BOTTOM

        self.info_panel_x = self.screen_width - INFO_PANEL_WIDTH + 10
        self.info_panel_y = PLOT_MARGIN_TOP

        if self.plot_width < 50: self.plot_width = 50
        if self.plot_height < 50: self.plot_height = 50

    def safe_coolprop_call(self, output_param, input1_param, input1_val, input2_param, input2_val, refrigerant):
        """Wrapper for CoolProp calls (expects SI units) to handle errors."""
        try:
            inputs_ok = True
            for v in [input1_val, input2_val]:
                 if not isinstance(v, (int, float)) or not math.isfinite(v):
                     inputs_ok = False; break
            if not inputs_ok: raise ValueError(f"Invalid non-finite input")

            val = CP.PropsSI(output_param, input1_param, input1_val, input2_param, input2_val, refrigerant)
            if not math.isfinite(val): raise ValueError(f"CoolProp returned non-finite value ({output_param}={val})")
            return val
        except ValueError as e:
            err_msg = str(e).split('\n')[0]
            error_str = f"CP Error: {err_msg} calc {output_param}({input1_param}={(input1_val or 0):.1f},{input2_param}={(input2_val or 0):.1f})"
            if error_str not in self.errors: self.errors.append(error_str)
            return None

    def calculate_dome(self):
        """Calculates dome points (in SI) based on pressure range."""
        self.dome_h_si = {'liq': [], 'vap': []}
        self.dome_p_pa = []
        self.errors = [e for e in self.errors if "Dome" not in e]

        try:
            crit_p_pa = self.safe_coolprop_call('pcrit', '', 0, '', 0, REFRIGERANT)
            if crit_p_pa is None: return

            p_min_pa_calc = self.p_min_psia * PSIA_TO_PA
            p_max_pa_calc = self.p_max_psia * PSIA_TO_PA
            p_start_pa = max(1000, p_min_pa_calc)
            p_end_pa = min(p_max_pa_calc, crit_p_pa * 0.999)

            if p_start_pa >= p_end_pa:
                self.errors.append(f"Dome Calc: Invalid SI P range from PSIA.")
                return

            pressures_pa_log = np.logspace(np.log10(p_start_pa), np.log10(p_end_pa), 80)

            for p_pa in pressures_pa_log:
                h_liq_si = self.safe_coolprop_call('H', 'P', p_pa, 'Q', 0, REFRIGERANT)
                h_vap_si = self.safe_coolprop_call('H', 'P', p_pa, 'Q', 1, REFRIGERANT)
                if h_liq_si is not None and h_vap_si is not None:
                    self.dome_p_pa.append(p_pa)
                    self.dome_h_si['liq'].append(h_liq_si)
                    self.dome_h_si['vap'].append(h_vap_si)

            if p_end_pa > crit_p_pa * 0.9:
                 crit_h_si = self.safe_coolprop_call('H', 'P', crit_p_pa, 'Q', 0.5, REFRIGERANT)
                 if crit_h_si is not None:
                    p_crit_psia = crit_p_pa * PA_TO_PSIA
                    if self.p_min_psia <= p_crit_psia <= self.p_max_psia:
                        self.dome_p_pa.append(crit_p_pa)
                        self.dome_h_si['liq'].append(crit_h_si)
                        self.dome_h_si['vap'].append(crit_h_si)
        except Exception as e:
            error_str = f"Unexpected Dome Calc Error: {e}"
            if error_str not in self.errors: self.errors.append(error_str)


    def calculate_cycle(self):
        """Calculates state points (in SI) and performance metrics."""
        self.errors = [e for e in self.errors if "CoolProp Error:" not in e]
        self.state_points_si = {'1': {}, '2': {}, '2s': {}, '3': {}, '4': {}}
        self.performance = {'COP': None, 'Q_evap_btu_lb': None, 'W_comp_btu_lb': None, 'Q_cond_btu_lb': None}

        p_evap_pa = self.p_evap_psia * PSIA_TO_PA
        p_cond_pa = self.p_cond_psia * PSIA_TO_PA
        delta_T_sh_k = self.superheat_F * DELTA_F_TO_DELTA_K
        delta_T_sc_k = self.subcooling_F * DELTA_F_TO_DELTA_K

        if p_evap_pa >= p_cond_pa:
            self.errors.append("P_evap must be < P_cond"); return

        T_sat_evap_k = self.safe_coolprop_call('T', 'P', p_evap_pa, 'Q', 1, REFRIGERANT)
        T_sat_cond_k = self.safe_coolprop_call('T', 'P', p_cond_pa, 'Q', 0, REFRIGERANT)
        if T_sat_evap_k is None or T_sat_cond_k is None: return

        # Point 1
        T1_k = T_sat_evap_k + max(0.01, delta_T_sh_k)
        h1_si = self.safe_coolprop_call('H', 'P', p_evap_pa, 'T', T1_k, REFRIGERANT)
        s1_si = self.safe_coolprop_call('S', 'P', p_evap_pa, 'T', T1_k, REFRIGERANT)
        if None in [h1_si, s1_si]: return
        self.state_points_si['1'] = {'p': p_evap_pa, 'h': h1_si, 's': s1_si, 'T': T1_k, 'Q': 1.0}

        # Point 2s
        s2s_si = s1_si
        h2s_si = self.safe_coolprop_call('H', 'P', p_cond_pa, 'S', s2s_si, REFRIGERANT)
        T2s_k = self.safe_coolprop_call('T', 'P', p_cond_pa, 'S', s2s_si, REFRIGERANT)
        if None in [h2s_si, T2s_k]: return
        self.state_points_si['2s'] = {'p': p_cond_pa, 'h': h2s_si, 's': s2s_si, 'T': T2s_k, 'Q': None}

        # Point 2
        if self.eta_comp <= 0: self.errors.append("Comp eff must be > 0"); return
        w_comp_isentropic_si = h2s_si - h1_si
        if w_comp_isentropic_si <= 0:
             self.errors.append("Warning: Isentropic enthalpy rise <= 0"); w_comp_isentropic_si = 1e-3
        h2_si = h1_si + w_comp_isentropic_si / self.eta_comp
        T2_k = self.safe_coolprop_call('T', 'P', p_cond_pa, 'H', h2_si, REFRIGERANT)
        s2_si = self.safe_coolprop_call('S', 'P', p_cond_pa, 'H', h2_si, REFRIGERANT)
        if None in [T2_k, s2_si]: return
        self.state_points_si['2'] = {'p': p_cond_pa, 'h': h2_si, 's': s2_si, 'T': T2_k, 'Q': None}

        # Point 3
        T3_k = T_sat_cond_k - max(0.01, delta_T_sc_k)
        h3_si = self.safe_coolprop_call('H', 'P', p_cond_pa, 'T', T3_k, REFRIGERANT)
        s3_si = self.safe_coolprop_call('S', 'P', p_cond_pa, 'T', T3_k, REFRIGERANT)
        if None in [h3_si, s3_si]: return
        self.state_points_si['3'] = {'p': p_cond_pa, 'h': h3_si, 's': s3_si, 'T': T3_k, 'Q': 0.0}

        # Point 4
        h4_si = h3_si; p4_pa = p_evap_pa
        T4_k = self.safe_coolprop_call('T', 'P', p4_pa, 'H', h4_si, REFRIGERANT)
        s4_si = self.safe_coolprop_call('S', 'P', p4_pa, 'H', h4_si, REFRIGERANT)
        q4 = self.safe_coolprop_call('Q', 'P', p4_pa, 'H', h4_si, REFRIGERANT)
        if None in [T4_k, s4_si, q4]: return
        self.state_points_si['4'] = {'p': p4_pa, 'h': h4_si, 's': s4_si, 'T': T4_k, 'Q': q4}

        # Performance
        q_evap_si = h1_si - h4_si
        w_comp_actual_si = h2_si - h1_si
        q_cond_si = h2_si - h3_si
        self.performance['Q_evap_btu_lb'] = q_evap_si * J_KG_TO_BTU_LB
        self.performance['W_comp_btu_lb'] = w_comp_actual_si * J_KG_TO_BTU_LB
        self.performance['Q_cond_btu_lb'] = q_cond_si * J_KG_TO_BTU_LB
        if w_comp_actual_si is not None and w_comp_actual_si > 1e-6:
             self.performance['COP'] = q_evap_si / w_comp_actual_si
        else: self.performance['COP'] = None

    def map_coordinates(self, h_btu_lb, p_psia):
        """Maps enthalpy (BTU/lb) and pressure (PSIA - log scale) to screen coordinates."""
        if p_psia <= 1e-6: p_psia = self.p_min_psia
        if h_btu_lb is None or p_psia is None: return None
        log_p = np.log10(p_psia)
        if not (self.h_min_btu_lb <= h_btu_lb <= self.h_max_btu_lb and
                self.log_p_min <= log_p <= self.log_p_max): return None
        x = self.plot_x + ((h_btu_lb - self.h_min_btu_lb) / (self.h_max_btu_lb - self.h_min_btu_lb)) * self.plot_width
        y = self.plot_y + self.plot_height - ((log_p - self.log_p_min) / (self.log_p_max - self.log_p_min)) * self.plot_height
        return int(x), int(y)

    def draw_axes_and_labels(self, screen):
        """Draws the P-h diagram axes, labels, and ticks in Imperial units."""
        pygame.draw.rect(screen, GRAY, (self.plot_x, self.plot_y, self.plot_width, self.plot_height), 1)
        # X-axis
        axis_y = self.plot_y + self.plot_height
        pygame.draw.line(screen, GRAY, (self.plot_x, axis_y), (self.plot_x + self.plot_width, axis_y), 1)
        label_x = self.axis_font.render(f"Specific Enthalpy (BTU/lb)", True, WHITE)
        screen.blit(label_x, (self.plot_x + self.plot_width / 2 - label_x.get_width() / 2, axis_y + TICK_LABEL_PADDING + self.tick_font.get_height() + 5))
        num_h_ticks = 6
        for i in range(num_h_ticks):
            h_val = self.h_min_btu_lb + i * (self.h_max_btu_lb - self.h_min_btu_lb) / (num_h_ticks - 1)
            map_result = self.map_coordinates(h_val, self.p_min_psia)
            if map_result:
                x, _ = map_result
                pygame.draw.line(screen, GRAY, (x, axis_y), (x, axis_y + 4), 1)
                tick_label = self.tick_font.render(f"{h_val:.0f}", True, WHITE)
                screen.blit(tick_label, (x - tick_label.get_width() / 2, axis_y + 4 + TICK_LABEL_PADDING))
        # Y-axis
        axis_x = self.plot_x
        pygame.draw.line(screen, GRAY, (axis_x, self.plot_y), (axis_x, self.plot_y + self.plot_height), 1)
        label_y = self.axis_font.render(f"Pressure (PSIA, log)", True, WHITE)
        label_y = pygame.transform.rotate(label_y, 90)
        screen.blit(label_y, (axis_x - AXIS_LABEL_PADDING - label_y.get_width()/2, self.plot_y + self.plot_height / 2 - label_y.get_height() / 2))
        pressure_ticks_psia = [10, 20, 30, 50, 75, 100, 150, 200, 300, 400]
        for p_psia in pressure_ticks_psia:
             if self.p_min_psia <= p_psia <= self.p_max_psia:
                 map_result = self.map_coordinates(self.h_min_btu_lb, p_psia)
                 if map_result:
                     _, y = map_result
                     pygame.draw.line(screen, GRAY, (axis_x - 4, y), (axis_x, y), 1)
                     tick_label = self.tick_font.render(f"{p_psia}", True, WHITE)
                     screen.blit(tick_label, (axis_x - 4 - tick_label.get_width() - TICK_LABEL_PADDING, y - tick_label.get_height() / 2))

    def draw_dome(self, screen):
        """Draws the vapor dome using stored SI data converted to Imperial for plotting."""
        if not self.dome_p_pa or len(self.dome_p_pa) < 2: return
        points_liq_screen, points_vap_screen = [], []
        for i in range(len(self.dome_p_pa)):
            p_psia = self.dome_p_pa[i] * PA_TO_PSIA
            h_liq_btu = self.dome_h_si['liq'][i] * J_KG_TO_BTU_LB
            h_vap_btu = self.dome_h_si['vap'][i] * J_KG_TO_BTU_LB
            coord_liq = self.map_coordinates(h_liq_btu, p_psia)
            coord_vap = self.map_coordinates(h_vap_btu, p_psia)
            if coord_liq: points_liq_screen.append(coord_liq)
            if coord_vap: points_vap_screen.append(coord_vap)
        if len(points_liq_screen) > 1: pygame.draw.lines(screen, GRAY, False, points_liq_screen, 2)
        if len(points_vap_screen) > 1: pygame.draw.lines(screen, GRAY, False, points_vap_screen, 2)

    def handle_input(self, event):
        """Handles keyboard input for changing Imperial parameters."""
        recalculate = False
        if event.type == pygame.KEYDOWN:
            key = event.key; step_p_evap=1.0; step_p_cond=2.0; step_t=1.0; step_eta=0.01
            # Pressure
            if key == pygame.K_RIGHT: self.p_evap_psia += step_p_evap; recalculate = True
            elif key == pygame.K_LEFT: self.p_evap_psia -= step_p_evap; recalculate = True
            elif key == pygame.K_UP: self.p_cond_psia += step_p_cond; recalculate = True
            elif key == pygame.K_DOWN: self.p_cond_psia -= step_p_cond; recalculate = True
            # Temps
            elif key == pygame.K_s: self.superheat_F += step_t; recalculate = True
            elif key == pygame.K_x: self.superheat_F = max(0.1, self.superheat_F - step_t); recalculate = True
            elif key == pygame.K_a: self.subcooling_F += step_t; recalculate = True
            elif key == pygame.K_z: self.subcooling_F = max(0.1, self.subcooling_F - step_t); recalculate = True
            # Efficiency
            elif key == pygame.K_e: self.eta_comp = min(1.0, self.eta_comp + step_eta); recalculate = True
            elif key == pygame.K_d: self.eta_comp = max(0.1, self.eta_comp - step_eta); recalculate = True
            # Faults
            elif key == pygame.K_l: self.p_evap_psia -= 5.0; self.superheat_F += 10.0; recalculate = True
            elif key == pygame.K_h: self.p_cond_psia += 10.0; self.superheat_F = max(1.0, self.superheat_F - 10.0); recalculate = True
            elif key == pygame.K_c: self.p_cond_psia += 10.0; recalculate = True
            elif key == pygame.K_v: self.p_evap_psia -= 5.0; recalculate = True
            # Reset
            elif key == pygame.K_r: self.reset_parameters(); recalculate = True
            # Fullscreen/Exit handled by App

            if recalculate:
                self.p_evap_psia = max(self.p_min_psia, min(self.p_max_psia - 2.0, self.p_evap_psia))
                self.p_cond_psia = max(self.p_evap_psia + 5.0, min(self.p_max_psia, self.p_cond_psia))
                self.calculate_cycle()

    def draw(self, screen):
        """Draws all base simulation elements onto the screen."""
        # This method will be overridden by the Viz class, but good to have a basic version
        screen.fill(BLACK)
        self.draw_axes_and_labels(screen)
        self.draw_dome(screen)
        # Base class doesn't draw cycle - Viz class will handle that
        # self.draw_cycle(screen) # If needed in base
        # self.draw_info_panel(screen) # If needed in base


# --- V4 Visualization Simulation Class ---
class RefrigerationSimImperialViz(RefrigerationSimImperial):
    def __init__(self, screen_width, screen_height):
        super().__init__(screen_width, screen_height) # Call base class constructor

        # Add specific fonts for visualization
        try:
            self.component_font = pygame.font.SysFont("Arial", 13, italic=True)
            self.legend_font = pygame.font.SysFont("Consolas", 13)
            self.state_desc_font = pygame.font.SysFont("Consolas", 13, bold=True)
        except Exception as e:
             print(f"Viz font load error: {e}. Using defaults from base.")
             # Fallback to fonts defined in the base class __init__
             self.component_font = self.small_font
             self.legend_font = self.small_font
             self.state_desc_font = self.small_font

    def get_state_description(self, state_name):
        """Determines the thermodynamic state based on calculated SI values."""
        state_si = self.state_points_si.get(state_name)
        if not state_si or not all(k in state_si for k in ['p', 'T']): return "Unknown/Error"

        p_pa = state_si['p']; T_k = state_si['T']; quality = state_si.get('Q')
        T_sat_k = self.safe_coolprop_call('T', 'P', p_pa, 'Q', 0.5, REFRIGERANT)
        if T_sat_k is None: return "Sat Temp Error"

        tol = 0.1 # K tolerance

        if quality is not None:
            if abs(quality - 0.0) < 1e-4 and T_k < (T_sat_k - tol): return "Subcooled Liquid"
            elif abs(quality - 0.0) < 1e-4: return "Saturated Liquid"
            elif abs(quality - 1.0) < 1e-4 and T_k > (T_sat_k + tol): return "Superheated Vapor"
            elif abs(quality - 1.0) < 1e-4: return "Saturated Vapor"
            elif 0.0 < quality < 1.0: return "Two-Phase Mixture"
            # Fall through if quality is weird (e.g., > 1)

        if T_k < (T_sat_k - tol): return "Subcooled Liquid"
        elif T_k > (T_sat_k + tol): return "Superheated Vapor"
        else: # Near saturation, check enthalpy as fallback
             h_si = state_si.get('h'); h_tol_j = 50 # J/kg enthalpy tolerance
             if h_si:
                 h_liq = self.safe_coolprop_call('H','P',p_pa,'Q',0,REFRIGERANT)
                 h_vap = self.safe_coolprop_call('H','P',p_pa,'Q',1,REFRIGERANT)
                 if h_liq and h_vap:
                     if abs(h_si - h_liq) < h_tol_j: return "Saturated Liquid"
                     if abs(h_si - h_vap) < h_tol_j: return "Saturated Vapor"
                     if h_liq < h_si < h_vap: return "Two-Phase Mixture"
             return "Near Saturation"

    # Override draw_cycle to add component labels and styled points
    def draw_cycle(self, screen):
        coords = {}
        state_points_imperial = {}
        for name, state_si in self.state_points_si.items():
            if state_si and all(k in state_si for k in ['p', 'h', 'T']):
                p_psia = state_si['p'] * PA_TO_PSIA; h_btu = state_si['h'] * J_KG_TO_BTU_LB; T_f = kelvin_to_fahrenheit(state_si['T'])
                state_points_imperial[name] = {'p': p_psia, 'h': h_btu, 'T': T_f, 'Q': state_si.get('Q')}
                coords[name] = self.map_coordinates(h_btu, p_psia)
            else: coords[name] = None

        # Lines and Labels
        line_defs = [
            ('1', '2s', PURPLE, "Ideal Comp.", True), ('1', '2', RED, "Compressor", False),
            ('2', '3', ORANGE, "Condenser", False), ('3', '4', BLUE, "Expansion", False),
            ('4', '1', GREEN, "Evaporator", False),
        ]
        for p1, p2, color, label, dashed in line_defs:
            c1, c2 = coords.get(p1), coords.get(p2)
            if c1 and c2:
                if dashed: draw_dashed_line(screen, color, c1, c2, dash_length=5)
                else: pygame.draw.line(screen, color, c1, c2, 2)
                if not dashed and label:
                    mx, my = (c1[0]+c2[0])//2, (c1[1]+c2[1])//2
                    angle = math.atan2(c2[1]-c1[1], c2[0]-c1[0])
                    ox, oy = -math.sin(angle)*COMPONENT_LABEL_OFFSET, math.cos(angle)*COMPONENT_LABEL_OFFSET
                    if abs(c1[1]-c2[1]) < 5 : oy *= -1.5 # Adjust horizontal
                    if abs(c1[0]-c2[0]) < 5 : ox *= 1.5  # Adjust vertical
                    lsurf = self.component_font.render(label, True, CYAN)
                    lrect = lsurf.get_rect(center=(mx + ox, my + oy))
                    screen.blit(lsurf, lrect)

        # Points and Temp Labels
        p_colors = {'1':GREEN, '2':RED, '2s':PURPLE, '3':ORANGE, '4':BLUE}; radius=5; lbl_off=7
        for name, coord in coords.items():
            if coord:
                color = p_colors.get(name, WHITE)
                pygame.draw.circle(screen, color, coord, radius + 1)
                pygame.draw.circle(screen, BLACK, coord, radius -1)
                pygame.draw.circle(screen, color, coord, radius -2)
                if name != '2s':
                    lnum = self.small_font.render(name, True, WHITE)
                    screen.blit(lnum, (coord[0]+lbl_off, coord[1]-lbl_off-lnum.get_height()))
                temp_f = state_points_imperial.get(name, {}).get('T')
                if temp_f is not None:
                    t_txt = f"{temp_f:.0f}°F" if name != '2s' else f"2s: {temp_f:.0f}°F"
                    t_color = PURPLE if name == '2s' else CYAN
                    t_lbl = self.tick_font.render(t_txt, True, t_color)
                    screen.blit(t_lbl, (coord[0]+lbl_off, coord[1]+lbl_off))

    # Override draw_info_panel to add state descriptions and legend
    def draw_info_panel(self, screen):
        panel_x = self.info_panel_x; y_pos = self.info_panel_y
        line_h = self.info_font.get_height() + 4; sml_line_h = self.small_font.get_height() + 3
        leg_line_h = self.legend_font.get_height() + 3; st_line_h = self.state_desc_font.get_height() + 3
        sec_space = 12

        # Title
        title_surf = self.title_font.render(f"{REFRIGERANT} Cycle (Imperial Viz)", True, WHITE)
        screen.blit(title_surf, (panel_x, y_pos)); y_pos += title_surf.get_height() + sec_space*1.5

        # Parameters
        p_title = self.info_font.render("Parameters:", True, YELLOW); screen.blit(p_title, (panel_x, y_pos)); y_pos += line_h
        T_evap_f = kelvin_to_fahrenheit(self.safe_coolprop_call('T','P',self.p_evap_psia*PSIA_TO_PA,'Q',1,REFRIGERANT))
        T_cond_f = kelvin_to_fahrenheit(self.safe_coolprop_call('T','P',self.p_cond_psia*PSIA_TO_PA,'Q',0,REFRIGERANT))
        T_evap_s = f"{T_evap_f:.1f}" if T_evap_f else "---"; T_cond_s = f"{T_cond_f:.1f}" if T_cond_f else "---"
        params = [f"P_evap:    {self.p_evap_psia:6.1f} PSIA ({T_evap_s:>4s}°F)", f"P_cond:    {self.p_cond_psia:6.1f} PSIA ({T_cond_s:>4s}°F)",
                  f"Superheat: {self.superheat_F:6.1f} °F", f"Subcool:   {self.subcooling_F:6.1f} °F", f"Comp Eff:  {self.eta_comp:6.2f}"]
        for line in params: screen.blit(self.info_font.render(line, True, WHITE), (panel_x, y_pos)); y_pos += line_h
        y_pos += sec_space

        # Performance
        perf_title=self.info_font.render("Performance:", True, YELLOW); screen.blit(perf_title,(panel_x, y_pos)); y_pos += line_h
        cop_s = f"{self.performance.get('COP', 0.0):.3f}" if self.performance.get('COP') else "---"
        q_evap_s = f"{self.performance.get('Q_evap_btu_lb', 0):.1f}" if self.performance.get('Q_evap_btu_lb') else "---"
        w_comp_s = f"{self.performance.get('W_comp_btu_lb', 0):.1f}" if self.performance.get('W_comp_btu_lb') else "---"
        q_cond_s = f"{self.performance.get('Q_cond_btu_lb', 0):.1f}" if self.performance.get('Q_cond_btu_lb') else "---"
        perf_data = [f"COP:       {cop_s:>7s}", f"Q_evap:    {q_evap_s:>7s} BTU/lb",
                     f"W_comp:    {w_comp_s:>7s} BTU/lb", f"Q_cond:    {q_cond_s:>7s} BTU/lb"]
        for line in perf_data: screen.blit(self.info_font.render(line, True, WHITE), (panel_x, y_pos)); y_pos += line_h
        y_pos += sec_space

        # State Descriptions
        st_desc_title = self.info_font.render("State Descriptions:", True, YELLOW); screen.blit(st_desc_title, (panel_x, y_pos)); y_pos += line_h
        for i in ['1','2','3','4']:
            desc = self.get_state_description(i); st_str = f"{i}: {desc}"
            screen.blit(self.state_desc_font.render(st_str, True, WHITE), (panel_x, y_pos)); y_pos += st_line_h
        y_pos += sec_space

        # State Points Data
        sp_title = self.info_font.render("State Points Data (P, T, h):", True, YELLOW); screen.blit(sp_title, (panel_x, y_pos)); y_pos += line_h
        for i in ['1','2','2s','3','4']:
            st_si = self.state_points_si.get(i)
            if st_si and all(k in st_si for k in ['p','h','T']):
                p, h, T = st_si['p']*PA_TO_PSIA, st_si['h']*J_KG_TO_BTU_LB, kelvin_to_fahrenheit(st_si['T'])
                q_s = f", q={st_si.get('Q', -1):.2f}" if st_si.get('Q') is not None and st_si.get('Q',-1)>=0 else ""
                st_str = f"{i:>2s}: P={p:<5.1f} T={T:<5.1f} h={h:<5.1f}{q_s}"; color = PURPLE if i == '2s' else WHITE
            else: st_str = f"{i:>2s}: (--- Calc Error ---)"; color = RED
            screen.blit(self.small_font.render(st_str, True, color), (panel_x, y_pos)); y_pos += sml_line_h
        y_pos += sec_space

        # Legend
        leg_title = self.info_font.render("Legend:", True, YELLOW); screen.blit(leg_title, (panel_x, y_pos)); y_pos += line_h
        leg_items = [(GREEN,"Evap Line/Pt 1"), (RED,"Actual Comp/Pt 2"), (ORANGE,"Cond Line/Pt 3"),
                     (BLUE,"Exp Line/Pt 4"), (PURPLE,"Ideal Comp/Pt 2s"), (CYAN,"Temp/Comp Labels"), (GRAY,"Dome/Axes")]
        for color, text in leg_items:
            pygame.draw.rect(screen, color, (panel_x, y_pos + 2, 10, 10))
            screen.blit(self.legend_font.render(text, True, WHITE), (panel_x + 15, y_pos)); y_pos += leg_line_h
        y_pos += sec_space

        # Controls (2 columns)
        ctrl_title = self.info_font.render("Controls:", True, YELLOW); screen.blit(ctrl_title, (panel_x, y_pos)); y_pos += line_h
        ctrls = ["[L/R Arr] P_evap +/- 1", "[U/D Arr] P_cond +/- 2", "[S/X] Superheat +/- 1",
                 "[A/Z] Subcool +/- 1", "[E/D] Comp Eff +/- 0.01", "[L] Low Charge", "[H] High Charge",
                 "[C] Dirty Cond.", "[V] Dirty Evap.", "[R] Reset", "[F] Fullscreen", "[Esc] Exit"]
        half_ctrl = (len(ctrls) + 1) // 2; col1_y = y_pos; col2_y = y_pos; col_w = INFO_PANEL_WIDTH // 2 - 5
        for i, line in enumerate(ctrls):
            surf = self.small_font.render(line, True, WHITE)
            if i < half_ctrl: screen.blit(surf, (panel_x, col1_y)); col1_y += sml_line_h
            else: screen.blit(surf, (panel_x + col_w, col2_y)); col2_y += sml_line_h
        y_pos = max(col1_y, col2_y) + sec_space

        # Errors (at bottom)
        if self.errors:
            max_h = self.screen_height - PLOT_MARGIN_TOP - 10
            err_y = max(y_pos, max_h - (len(self.errors[-5:])+1)*sml_line_h - line_h)
            err_title = self.info_font.render("Errors/Warnings:", True, RED); screen.blit(err_title, (panel_x, err_y)); y_pos = err_y + line_h
            for error in self.errors[-5:]:
                 if y_pos > max_h: break
                 max_l = INFO_PANEL_WIDTH // (self.small_font.size("W")[0]*0.9)
                 err_s = error if len(error)<=max_l else error[:int(max_l)-3]+"..."
                 screen.blit(self.small_font.render(err_s, True, RED), (panel_x, y_pos)); y_pos += sml_line_h

    # Override the main draw method to call the overridden cycle/panel draws
    def draw(self, screen):
        screen.fill(BLACK)
        self.draw_axes_and_labels(screen)
        self.draw_dome(screen)
        self.draw_cycle(screen) # Calls the Viz version of draw_cycle
        self.draw_info_panel(screen) # Calls the Viz version of draw_info_panel


# --- Helper Function for Dashed Line ---
def draw_dashed_line(surf, color, start_pos, end_pos, width=1, dash_length=5):
    x1, y1 = start_pos; x2, y2 = end_pos; dl = dash_length
    if (x1 == x2 and y1 == y2): return
    line_length = math.hypot(x2 - x1, y2 - y1)
    angle = math.atan2(y2 - y1, x2 - x1)
    num_dashes = int(line_length / (dl * 2))
    for i in range(num_dashes + 1):
        start_x = x1 + math.cos(angle) * (i * dl * 2); start_y = y1 + math.sin(angle) * (i * dl * 2)
        end_len = min(dl, line_length - (i * dl * 2))
        if end_len <= 0: break
        end_x = start_x + math.cos(angle) * end_len; end_y = start_y + math.sin(angle) * end_len
        pygame.draw.line(surf, color, (start_x, start_y), (end_x, end_y), width)

# --- Main Application Class ---
class App:
    def __init__(self):
        pygame.init()
        pygame.font.init()
        self.screen_flags = pygame.RESIZABLE | pygame.DOUBLEBUF
        self.screen = pygame.display.set_mode((INITIAL_SCREEN_WIDTH, INITIAL_SCREEN_HEIGHT), self.screen_flags)
        pygame.display.set_caption(f"Interactive P-h Diagram Simulator - {REFRIGERANT} (Imperial Viz)")
        self.clock = pygame.time.Clock()
        self.running = True
        # *** Use the Visualization simulation class ***
        self.sim = RefrigerationSimImperialViz(INITIAL_SCREEN_WIDTH, INITIAL_SCREEN_HEIGHT)

    def run(self):
        while self.running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT: self.running = False
                elif event.type == pygame.VIDEORESIZE:
                    w, h = max(MIN_SCREEN_WIDTH, event.w), max(MIN_SCREEN_HEIGHT, event.h)
                    self.screen = pygame.display.set_mode((w, h), self.screen_flags)
                    self.sim.screen_width, self.sim.screen_height = w, h
                    self.sim.update_layout(); self.sim.calculate_cycle()
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_f: # Fullscreen
                         self.sim.fullscreen = not self.sim.fullscreen
                         pygame.display.toggle_fullscreen()
                         w, h = pygame.display.get_surface().get_size()
                         self.sim.screen_width, self.sim.screen_height = w, h
                         self.sim.update_layout(); self.sim.calculate_cycle()
                    elif event.key == pygame.K_ESCAPE: # Exit Fullscreen or Quit
                        if self.sim.fullscreen:
                             self.sim.fullscreen = False; pygame.display.toggle_fullscreen()
                             w, h = pygame.display.get_surface().get_size()
                             self.sim.screen_width, self.sim.screen_height = w, h
                             self.sim.update_layout(); self.sim.calculate_cycle()
                        else: self.running = False
                    else: self.sim.handle_input(event) # Pass to sim class

            self.sim.draw(self.screen) # Calls RefrigerationSimImperialViz.draw()
            pygame.display.flip()
            self.clock.tick(60)
        pygame.quit(); sys.exit()

# --- Main Execution ---
if __name__ == '__main__':
    app = App()
    app.run()
