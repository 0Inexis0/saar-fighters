"""Isolated Python entry; import only from the root-owned installation directory."""
import sys
sys.path.insert(0, "/opt/saar-fighters")
from installer.backend import main
sys.exit(main())
