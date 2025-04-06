# Interactive P-h Diagram Simulator

This project provides an interactive, educational tool built with Pygame and CoolProp to help users understand Pressure-Enthalpy (P-h) diagrams in the context of vapor-compression refrigeration systems. Users can adjust parameters like superheat, subcooling, pressures, and compressor efficiency, and simulate common system faults to visualize their impact on the cycle.

This version currently displays data in Imperial units (PSIA, °F, BTU/lb) and includes visualizations for component processes and the difference between ideal (isentropic) and actual compression.

## Features (Current)

*   Displays the refrigeration cycle on a P-h diagram with a logarithmic pressure axis.
*   Uses CoolProp library for accurate refrigerant properties (currently configured for R134a).
*   Allows real-time adjustment of:
    *   Evaporating Pressure (P_evap)
    *   Condensing Pressure (P_cond)
    *   Superheat
    *   Subcooling
    *   Compressor Isentropic Efficiency
*   Simulates approximate effects of common faults:
    *   Low Charge
    *   High Charge
    *   Dirty Condenser Coil
    *   Dirty Evaporator Coil
*   Displays calculated performance metrics (COP, Q_evap, W_comp, Q_cond) in Imperial units.
*   Visualizes both ideal (isentropic, dashed line) and actual compression processes.
*   Labels components (Evaporator, Compressor, etc.) directly on the diagram lines.
*   Provides descriptions of the refrigerant state (Subcooled Liquid, Two-Phase, etc.) at key points.
*   Includes a legend explaining diagram colors.
*   Supports window resizing and fullscreen mode.

## Installation

1.  **Python:** Ensure you have Python 3 installed (Python 3.9+ recommended).
2.  **Virtual Environment (Recommended):**
    *   Navigate to the project directory in your terminal.
    *   Create a virtual environment:
        ```bash
        python3 -m venv venv
        ```
    *   Activate the environment:
        *   macOS/Linux: `source venv/bin/activate`
        *   Windows: `venv\Scripts\activate`
3.  **Install Dependencies:**
    *   With the virtual environment active, install the required libraries:
        ```bash
        pip install pygame CoolProp numpy
        ```

## Usage

1.  Activate your virtual environment (if using one).
2.  Run the main simulation script (assuming the final refactored entry point is `main.py`):
    ```bash
    python main.py
    ```
    *(If running the pre-refactoring `ph_simulator_v4.py` directly, use `python ph_simulator_v4.py`)*
3.  Use the keyboard controls displayed in the info panel to adjust parameters and observe changes on the P-h diagram. Key controls include:
    *   **Arrow Keys:** Adjust P_evap and P_cond.
    *   **S/X, A/Z, E/D:** Adjust Superheat, Subcooling, Efficiency.
    *   **L, H, C, V:** Simulate faults.
    *   **R:** Reset parameters to default.
    *   **F:** Toggle fullscreen.
    *   **Esc:** Exit fullscreen or quit the application.

## Refactoring Plan

This plan outlines steps to refactor the codebase (`ph_simulator_v4.py` stage) for improved modularity, readability, and maintainability.

**Goals:**

*   **Improve Modularity:** Break code into smaller, focused Python modules.
*   **Increase Readability:** Make code easier to understand and follow.
*   **Enhance Maintainability:** Simplify bug fixing and feature additions.
*   **Apply Single Responsibility Principle (SRP):** Ensure classes/functions have one clear purpose.
*   **Prepare for Future Expansion:** Create a more flexible structure.

---

### Phase 1: File Structure and Basic Separation

1.  **Separate Base Class**
    *   **Action:** Move the `RefrigerationSimImperial` class (V3 code) into `base_simulation.py`.
    *   **Reasoning:** Clear separation of the core calculation engine from visualization.
    *   **Impact:** Visualization module will import from `base_simulation`.

2.  **Create Utility Module**
    *   **Action:** Create `utils.py`. Move unit conversion constants, temperature conversion functions (`kelvin_to_fahrenheit`, etc.), and helper functions (`draw_dashed_line`) here.
    *   **Reasoning:** Consolidates reusable helpers and constants.
    *   **Impact:** Other modules will import from `utils`.

3.  **Create Configuration Module**
    *   **Action:** Create `config.py`. Move global constants (screen dimensions, colors, `REFRIGERANT`, UI layout params, default sim params) here.
    *   **Reasoning:** Centralizes configuration settings.
    *   **Impact:** Other modules will import from `config`.

4.  **Rename Main Files**
    *   **Action:** Rename `ph_simulator_v4.py` to `visualization_simulation.py` (containing `RefrigerationSimImperialViz`). Create `main.py` for the `App` class and entry point (`if __name__ == '__main__':`).
    *   **Reasoning:** Separates the application runner from simulation logic.
    *   **Impact:** `main.py` becomes the executable script.

---

### Phase 2: Refactoring the Simulation/Visualization Class

5.  **Extract Diagram Drawing Logic**
    *   **Action:** Create `DiagramDrawer` class in `drawing.py` (or `ui_components.py`). Move `draw_axes_and_labels`, `draw_dome`, and the visual parts of `draw_cycle` here.
    *   **Reasoning:** Separates complex drawing logic from simulation state (SRP).
    *   **Impact:** `visualization_simulation.py` will instantiate and use `DiagramDrawer`. `map_coordinates` might move to `utils.py` or `DiagramDrawer`.

6.  **Extract Info Panel Logic**
    *   **Action:** Create `InfoPanel` class (in `ui_components.py`). Move logic from `draw_info_panel` into focused methods within this class (e.g., `draw_parameters`, `draw_performance`, etc.).
    *   **Reasoning:** Manages the complexity of the info panel separately (SRP).
    *   **Impact:** `visualization_simulation.py` will instantiate and use `InfoPanel`, passing necessary data.

7.  **Refine State Description Logic**
    *   **Action:** Move `get_state_description` to `utils.py` or a small dedicated `StateAnalyzer` class.
    *   **Reasoning:** Separates pure data analysis function.
    *   **Impact:** `InfoPanel` will call this utility.

---

### Phase 3: Refining Interactions and Readability

8.  **Improve Data Flow**
    *   **Action:** Review data passing between Simulation, Drawer, and InfoPanel. Use clean interfaces (e.g., pass data dictionaries/objects).
    *   **Reasoning:** Reduces tight coupling, clarifies dependencies.
    *   **Impact:** May require changes to method signatures.

9.  **Enhance Readability**
    *   **Action:** Add docstrings, type hints. Break down long methods. Ensure consistent naming. Replace magic numbers with constants from `config.py`.
    *   **Reasoning:** Improves understanding and code quality.
    *   **Impact:** More self-documenting and robust code.

10. **Review Input Handling**
    *   **Action:** Consider decoupling input detection (`handle_input`) from immediate calculation triggering. `handle_input` could set flags, and the main loop could trigger calculations based on flags.
    *   **Reasoning:** Slightly better separation of concerns (input vs. action).
    *   **Impact:** Minor changes to input handling and the main `App` loop.

---

### Tools and Practices

*   **Version Control:** Use Git and commit frequently after each step.
*   **Testing:** Add basic unit tests for utilities and core calculations if possible.
*   **Incremental Approach:** Perform refactoring steps one by one, testing thoroughly after each change.

## Future Enhancements (Post-Refactoring)

*   Support for selecting different refrigerants.
*   Graphical User Interface elements (sliders, buttons) using a Pygame GUI library.
*   More detailed and physically accurate fault modeling.
*   Ability to save/load simulation parameters or states.
*   Option to plot lines of constant entropy or temperature on the diagram.
*   Export diagram/data functionality.
