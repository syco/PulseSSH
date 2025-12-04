#!/usr/bin/env python3
import json
import os
import sys
import time

LOG_FILE = os.path.expanduser("~/pulse_ssh_orchestrator.log")

def log_to_file(message):
    with open(LOG_FILE, "a") as f:
        f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}\n")

def send_command(command_obj):
    json_str = json.dumps(command_obj)
    log_to_file(f"Send: {json_str}")
    print(json_str, flush=True)

def main():
    if os.path.exists(LOG_FILE):
        os.remove(LOG_FILE)

    i = 0
    while ++i < 10:
        command_to_run = {'action': 'get-last-line'}
        send_command(command_to_run)
        line = sys.stdin.readline().strip()
        log_to_file(f"Received: <{line}>")
        if line.endswith(('$', '#', '>', '%')):
            break
        else:
            time.sleep(1)

    command_to_run = {'action': 'get-variable', 'data': '{user}'}
    send_command(command_to_run)
    line = sys.stdin.readline().strip()
    log_to_file(f"Received: <{line}>")
    time.sleep(1)

    command_to_run = {'action': 'feed-child', 'data': 'whoami'}
    send_command(command_to_run)

    command_to_run = {'action': 'feed', 'data': 'This is a message'}
    send_command(command_to_run)

    sys.exit(0)

if __name__ == "__main__":
    main()
