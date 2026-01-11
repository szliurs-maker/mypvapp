# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **Streamlit-based web application** for evaluating commercial and industrial (C&I) distributed photovoltaic (PV) solar systems. It performs financial analysis including ROI, IRR, DSCR calculations and helps design solar panel installations.

## Common Commands

```bash
# Run the app in development mode
streamlit run app18.py

# Build Windows executable (one-dir mode)
pyinstaller --onedir --name "my_pv_quotation" my_pv_quotation.spec

# Build single-file executable
pyinstaller --onefile --name "my_pv_quotation" run_app.py

# Install dependencies
venv\Scripts\activate && pip install -r requirements.txt
```

## Architecture

**Single-file Streamlit app pattern** in `app18.py`:

1. **Configuration** (lines 14-42): Session state, technical attributes (TOPCON, BC panels), cost databases
2. **Sidebar Input** (lines 47-71): Location, efficiency, soft costs, financial parameters (loan terms, electricity price)
3. **Financial Engine** (`run_finance_engine_v13()`): 25-year pro forma modeling with VAT, loan amortization, DSCR analysis
4. **UI Rendering** (lines 123-224): Satellite mapping with polygon drawing, scheme comparison, Plotly charts, stress testing

**Key technical details**:
- Uses `st.session_state` for `confirmed_area` and `active_scheme`
- Geodetic calculations use WGS84 ellipsoid
- Inverter replacement cost at year 10
- Guangdong benchmark electricity price: 0.453 RMB/kWh

## Key Dependencies

- `streamlit==1.52.2` - Web UI
- `pandas==2.3.3`, `numpy==2.4.0` - Data processing
- `numpy-financial==1.0.0` - Financial calculations
- `plotly==6.5.0` - Charts
- `folium==0.20.0`, `streamlit-folium==0.25.3` - Mapping
- `shapely==2.1.2`, `pyproj==3.7.2`, `geopy==2.4.1` - Geospatial
- `pyinstaller==6.17.0` - Windows executable packaging

## Entry Points

- `app18.py` - Main application
- `run_app.py` - PyInstaller entry point
- `my_pv_quotation.spec` - PyInstaller configuration
