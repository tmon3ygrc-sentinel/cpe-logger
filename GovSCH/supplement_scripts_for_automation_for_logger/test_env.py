from pathlib import Path
env_path = Path(".env").read_text()
print(f"RAW FILE CONTENT START:\n{env_path}\nRAW FILE CONTENT END")