import sys
import time

num_seconds = int(sys.argv[1]) if len(sys.argv) > 1 else 100

print(f"running for {num_seconds}s",)

for i in range(num_seconds):
    print("HERE", i + 1, file=sys.stdout if i % 2 == 0 else sys.stderr)
    time.sleep(1)

print("exiting successfully")
