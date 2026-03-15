# run.py
from api.app import create_app

app = create_app()

if __name__ == "__main__":
    import sys
    try:
        app.run(debug=True)
    except KeyboardInterrupt:
        print("Server gracefully stopped.")
    except OSError as e:
        if getattr(e, 'winerror', None) == 10038:
            print("Server gracefully stopped (socket released).")
        else:
            raise
    except BaseException:     
        sys.exit(0)
