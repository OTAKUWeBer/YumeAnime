# run.py
import os
from api.app import create_app

app = create_app()

if __name__ == "__main__":
    import sys
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    try:
        app.run(host=host, port=port, debug=debug, use_reloader=False)
    except KeyboardInterrupt:
        print("Server gracefully stopped.")
    except OSError as e:
        if getattr(e, 'winerror', None) == 10038:
            print("Server gracefully stopped (socket released).")
        else:
            raise
    except BaseException:
        sys.exit(0)
