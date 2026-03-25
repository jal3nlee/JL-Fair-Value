# JL Fair Value - DCF Valuation Model 📊

Professional discounted cash flow (DCF) valuation tool with dual terminal value methods.

## Features ✨

- **iXBRL Parsing** - Automatic extraction from SEC 10-K HTML filings
- **Dual Terminal Value** - Gordon Growth + Exit Multiple methods
- **Revenue Growth Plateau** - 2-year plateau before terminal growth
- **CAPEX Fade Logic** - Linear fade from initial to terminal
- **Scenario Analysis** - Bear/Base/Bull cases
- **Sensitivity Tables** - WACC × Terminal Growth, Exit Multiple × Revenue Growth
- **Reverse DCF** - Market-implied growth solver

## Quick Start

### Using the Live App
👉 **[Launch App](https://jl-fair-value.streamlit.app)** (once deployed)

### Run Locally
```bash
# Clone the repo
git clone https://github.com/jal3nlee/JL-Fair-Value.git
cd JL-Fair-Value

# Install dependencies
pip install -r requirements.txt

# Run the app
streamlit run app.py
```

## How to Use

1. **Get a 10-K filing** from [SEC EDGAR](https://www.sec.gov/edgar/searchedgar/companysearch.html)
2. **Upload the HTML file** in the app sidebar
3. **Adjust assumptions** using the sliders
4. **Analyze results** in the tabs (Projection, Scenarios, Sensitivity, Reverse DCF)

## Project Structure
```
JL-Fair-Value/
├── app.py                    # Main Streamlit application
├── requirements.txt          # Python dependencies
├── src/
│   ├── data/
│   │   └── sec_parser.py    # iXBRL extraction
│   ├── valuation/
│   │   ├── dcf_engine.py    # Core DCF calculations
│   │   ├── reverse_dcf.py   # Implied growth solver
│   │   └── sensitivity.py   # Sensitivity analysis
│   └── utils/
│       └── formatters.py    # Display utilities
└── .streamlit/
    └── config.toml          # Streamlit config
```

## License

MIT License - See LICENSE file for details
