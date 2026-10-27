"""logisim-forge: build Logisim circuits from code, verify them with Logisim itself."""
from .circuit import Circuit
from .verify import Netlist, Report, dump, normalize, parse, verify
from .simulate import inspect, simulate

__all__ = ["Circuit", "Netlist", "Report", "dump", "normalize", "parse", "verify", "inspect", "simulate"]
__version__ = "0.2.0"
