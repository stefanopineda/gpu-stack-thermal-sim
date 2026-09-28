# gpusim

Compact airflow and thermal-network simulator for air-cooled multi-GPU workstations.

GPU water blocks are out of scope. This is not CFD. Temperatures are in degrees Celsius.
Default ambient is 25 °C.

Typical accuracy is about ±5–10 °C absolute. The model is more trustworthy for ranking configurations than for absolute temperatures.

See `SPEC.md` for revision 3. Install and usage are documented below once the package is complete.

```bash
uv venv
uv pip install -e ".[dev]"
```
