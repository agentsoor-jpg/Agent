"""Logger"""
import time
class Logger:
    def __init__(self): self.entries=[]
    def info(self, msg, src="system"): self.entries.append(f"[{time.strftime("%H:%M:%S")}] [INFO] [{src}] {msg}")
    def error(self, msg, src="system"): self.entries.append(f"[{time.strftime("%H:%M:%S")}] [ERROR] [{src}] {msg}")
