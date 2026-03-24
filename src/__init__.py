"""clang-call-analyzer - C/C++ function call analyzer."""

__version__ = '1.0.0'

# Re-export all modules (except cli to avoid circular import warnings when using as module)
# from . import cli
from . import compilation_db
from . import ast_parser
from . import function_extractor
from . import function_registry
from . import call_analyzer
from . import relationship_builder
from . import json_emitter
from . import file_graph_generator
from . import compile_commands_simplifier
from . import doxygen_parser
from . import echarts_templates
