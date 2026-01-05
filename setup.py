import os
import re

TARGETS_FILE = "targets.txt"
EMAILS_FILE = "emails.txt"

def ask_targets():
    print("Targets (IPs / Domains)")
    print("One per line - ENTER to finish:")
    targets = []
    while True:
        val = input("> ").strip()
        if not val:
            break
        targets.append(val)
    return targets

def ask_emails():
    print("Receiver emails (comma-separated, no spaces)")
    raw = input("> ")
    cleaned = raw.replace(" ", "")
    emails = [e for e in cleaned.split(",") if e]

    invalid = [e for e in emails if not re.match(r"^[^@]+@[^@]+\.[^@]+$", e)]
    if invalid:
        print("Invalid email(s):", ", ".join(invalid))
        print("Please enter again.\n")
        return ask_emails()
    return ",".join(emails)

if not os.path.exists(TARGETS_FILE):
    targets = ask_targets()
    if not targets:
        print("No targets entered – aborting")
        exit(1)
    with open(TARGETS_FILE, "w") as f:
        f.write("\n".join(targets))
    print(f"{TARGETS_FILE} created.")

if not os.path.exists(EMAILS_FILE):
    emails = ask_emails()
    with open(EMAILS_FILE, "w") as f:
        f.write(emails + "\n")
    print(f"{EMAILS_FILE} created.")

print("Setup completed!")
