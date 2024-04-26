import logging
import subprocess

from app import create_app

app = create_app()

if __name__ == "__main__":
    subprocess.Popen("""ngrok.exe http 8000 --domain weevil-boss-generally.ngrok-free.app""", shell=True)
    subprocess.Popen(app.run(host="0.0.0.0", port=8000))