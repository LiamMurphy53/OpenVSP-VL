"""Stop only a run's isolated process group, including stubborn solver children."""
import os,signal,time
STOP_GRACE_SECONDS=3.

def stop_group(pid,process=None):
    def send(sig):
        try:os.killpg(pid,sig);return True
        except ProcessLookupError:return False
    def exists():
        if process is not None:process.poll()
        return send(0)
    send(signal.SIGTERM);deadline=time.monotonic()+STOP_GRACE_SECONDS;forced=False
    while exists():
        if time.monotonic()>=deadline:
            forced=send(signal.SIGKILL);break
        time.sleep(.025)
    if process is not None:process.wait(timeout=5)
    return forced
