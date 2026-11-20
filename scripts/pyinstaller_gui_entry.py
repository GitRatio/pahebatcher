"""PyInstaller entry point: native Bunny Takeover webview; --classic is the Tk fallback."""

import sys

if __name__ == "__main__":
    if "--classic" in sys.argv:
        from pahebatcher.gui.app import main
    else:
        from pahebatcher.gui.webui import main
    main()
