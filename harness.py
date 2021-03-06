import time
import os
import sys
import sqlite3
import threading
from subprocess import Popen, PIPE
from utils import (getdevices, generatedatabase, forwardlocalhosts, 
        getlog, launchbrowser, DBNAME, CONFIG)


LOGS = {}
LOGSDIR = CONFIG['logsdir']
MONITORS = {}
PORT = CONFIG['port'] #Have to define here for now to do forwarding in harness

"""Consider storing fuzzstatus in db, and controlling from here?"""
"""Also consider filtering out D/W messages in logcat."""

CRASHPATTERN = "SIGSEG"

def monitordevice(devname):
    while True:
        res = getdevices()
        print(res)
        if len([d for d in getdevices() if devname in d]) > 0:
            #devname not in getdevices():
            print("Couldn't find the device:", devname)
            LOGS.pop(devname)
            return
        print("Monitoring ", devname)
        try:
            logname = LOGS[devname]['logname']
            tombstone = ""
            #grep = Popen(['grep', CRASHPATTERN], stdin=PIPE, stdout=PIPE)
            proc = Popen(['adb', '-s', devname, 'logcat'], stdout=PIPE)
            while True:
                crashlog = ""
                line = proc.stdout.readline().decode("utf-8")
                nocrash = True
                if CRASHPATTERN in line:
                    nocrash = False
                if nocrash:
                    continue
                print("Got a crash?")
                print(devname, '--', line)
                #Handle it below.
                crashlog += line
                #Read out the rest of the backtrace.
                foundtombstone = False
                while True:
                    follow = proc.stdout.readline().decode("utf-8")
                    crashlog += follow
                    #This condition works for Nexus 5
                    if "tombstone" in follow:
                        for word in follow.split():
                            if "tombstone" in word:
                                tombstone = word
                                print("Tombstone:", tombstone)
                                foundtombstone=True
                                break
                    if foundtombstone:
                        break
                perm = 'w'
                if os.path.exists(logname):
                    perm = 'a'
                with open(logname, perm) as f:
                    f.seek(0, os.SEEK_END)
                    logpos = f.tell()
                    f.write(crashlog)
                    while True:
                        try:
                            with sqlite3.connect(DBNAME) as conn:
                                conn.execute("""INSERT INTO crashes(logpos, logpath)
                                    VALUES(?,?)""", (logpos,logname))
                                break
                        except sqlite3.OperationalError:
                            print("Waiting for Database to unlock...")
        except:
            print("Exception thrown in harness thread.")
            print(sys.exc_info())
            continue

def main():
    """Where the main loop resides.
    Want to parse the logs of each set of devices, and take actions
    depending on what we find.
    
    We should ideally start a new thread for each of these devices."""
    while True:
        DEVICES = getdevices()
        forwardlocalhosts(PORT)
        for i in DEVICES:
            if i['name'] not in LOGS:
                print("Device is new:", i['name'])
                #logname = getlog(i['name']) #+ "-log.txt")
                LOGS[i['name']] = {'logname':getlog(i['name'])}
                monitorthread = threading.Thread(target=monitordevice, \
                        kwargs={'devname':i['name']})
                monitorthread.start()
        time.sleep(1.5)
    pass

if __name__ == "__main__":
    generatedatabase()
    main()
