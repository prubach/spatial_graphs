import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dash_graphs import create_app

# Dash serves under CONTEXT_PATH (default "spatialgraph"), so mount the WSGI app at "/".
application = create_app(pdbid="1A8E", is_topoly=False).server
