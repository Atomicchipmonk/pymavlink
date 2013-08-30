#!/usr/bin/env python

'''
fit best estimate of magnetometer rotation to gyro data
'''

import sys, time, os, math

from optparse import OptionParser
parser = OptionParser("magfit_rotation_gyro.py [options]")
parser.add_option("--no-timestamps",dest="notimestamps", action='store_true', help="Log doesn't have timestamps")
parser.add_option("--verbose", action='store_true', help="verbose output")
parser.add_option("--min-rotation", default=5.0, type='float', help="min rotation to add point")

(opts, args) = parser.parse_args()

from pymavlink import mavutil
from pymavlink.rotmat import Vector3, Matrix3
from math import radians, degrees

if len(args) < 1:
    print("Usage: magfit_rotation_gyro.py [options] <LOGFILE...>")
    sys.exit(1)

class Rotation(object):
    def __init__(self, name, roll, pitch, yaw):
        self.name = name
        self.roll = roll
        self.pitch = pitch
        self.yaw = yaw
        self.r = Matrix3()
        self.r.from_euler(self.roll, self.pitch, self.yaw)

    def is_90_degrees(self):
        return (self.roll % 90 == 0) and (self.pitch % 90 == 0) and (self.yaw % 90 == 0)

    def __str__(self):
        return self.name

# the rotations used in APM
rotations = [
    Rotation("ROTATION_NONE",                      0,   0,   0),
    Rotation("ROTATION_YAW_45",                    0,   0,  45),
    Rotation("ROTATION_YAW_90",                    0,   0,  90),
    Rotation("ROTATION_YAW_135",                   0,   0, 135),
    Rotation("ROTATION_YAW_180",                   0,   0, 180),
    Rotation("ROTATION_YAW_225",                   0,   0, 225),
    Rotation("ROTATION_YAW_270",                   0,   0, 270),
    Rotation("ROTATION_YAW_315",                   0,   0, 315),
    Rotation("ROTATION_ROLL_180",                180,   0,   0),
    Rotation("ROTATION_ROLL_180_YAW_45",         180,   0,  45),
    Rotation("ROTATION_ROLL_180_YAW_90",         180,   0,  90),
    Rotation("ROTATION_ROLL_180_YAW_135",        180,   0, 135),
    Rotation("ROTATION_PITCH_180",                 0, 180,   0),
    Rotation("ROTATION_ROLL_180_YAW_225",        180,   0, 225),
    Rotation("ROTATION_ROLL_180_YAW_270",        180,   0, 270),
    Rotation("ROTATION_ROLL_180_YAW_315",        180,   0, 315),
    Rotation("ROTATION_ROLL_90",                  90,   0,   0),
    Rotation("ROTATION_ROLL_90_YAW_45",           90,   0,  45),
    Rotation("ROTATION_ROLL_90_YAW_90",           90,   0,  90),
    Rotation("ROTATION_ROLL_90_YAW_135",          90,   0, 135),
    Rotation("ROTATION_ROLL_270",                270,   0,   0),
    Rotation("ROTATION_ROLL_270_YAW_45",         270,   0,  45),
    Rotation("ROTATION_ROLL_270_YAW_90",         270,   0,  90),
    Rotation("ROTATION_ROLL_270_YAW_135",        270,   0, 135),
    Rotation("ROTATION_PITCH_90",                  0,  90,   0),
    Rotation("ROTATION_PITCH_270",                 0, 270,   0),    
    Rotation("ROTATION_PITCH_180_YAW_90",          0, 180,  90),    
    Rotation("ROTATION_PITCH_180_YAW_270",         0, 180, 270),    
    Rotation("ROTATION_ROLL_90_PITCH_90",         90,  90,   0),    
    Rotation("ROTATION_ROLL_180_PITCH_90",       180,  90,   0),    
    Rotation("ROTATION_ROLL_270_PITCH_90",       270,  90,   0),    
    Rotation("ROTATION_ROLL_90_PITCH_180",        90, 180,   0),    
    Rotation("ROTATION_ROLL_270_PITCH_180",      270, 180,   0),    
    Rotation("ROTATION_ROLL_90_PITCH_270",        90, 270,   0),    
    Rotation("ROTATION_ROLL_180_PITCH_270",      180, 270,   0),    
    Rotation("ROTATION_ROLL_270_PITCH_270",      270, 270,   0),    
    Rotation("ROTATION_ROLL_90_PITCH_180_YAW_90", 90, 180,  90),    
    Rotation("ROTATION_ROLL_90_YAW_270",          90,   0, 270)
    ]

def mag_fixup(mag, AHRS_ORIENTATION, COMPASS_ORIENT, COMPASS_EXTERNAL):
    '''fixup a mag vector back to original value using AHRS and Compass orientation parameters'''
    if COMPASS_EXTERNAL == 0 and AHRS_ORIENTATION != 0:
        # undo any board orientation
        mag = rotations[AHRS_ORIENTATION].r.transposed() * mag
    # undo any compass orientation
    if COMPASS_ORIENT != 0:
        mag = rotations[COMPASS_ORIENT].r.transposed() * mag
    return mag

def add_errors(mag, gyr, last_mag, deltat, total_error, rotations):
    for i in range(len(rotations)):
        if not rotations[i].is_90_degrees():
            continue
        r = rotations[i].r
        m = Matrix3()
        m.rotate(gyr * deltat)
        rmag1 = r * last_mag
        rmag2 = r * mag
        rmag3 = m.transposed() * rmag1
        err = rmag3 - rmag2
        total_error[i] += err.length()
        

def magfit(logfile):
    '''find best magnetometer rotation fit to a log file'''

    print("Processing log %s" % filename)
    mlog = mavutil.mavlink_connection(filename, notimestamps=opts.notimestamps)

    last_mag = None
    last_usec = 0
    count = 0
    total_error = [0]*len(rotations)

    AHRS_ORIENTATION = 0
    COMPASS_ORIENT = 0
    COMPASS_EXTERNAL = 0

    # now gather all the data
    while True:
        m = mlog.recv_match()
        if m is None:
            break
        if m.get_type() == "PARAM_VALUE":
            if str(m.param_id) == 'AHRS_ORIENTATION':
                AHRS_ORIENTATION = int(m.param_value)
            if str(m.param_id) == 'COMPASS_ORIENT':
                COMPASS_ORIENT = int(m.param_value)
            if str(m.param_id) == 'COMPASS_EXTERNAL':
                COMPASS_EXTERNAL = int(m.param_value)
        if m.get_type() == "RAW_IMU":
            mag = Vector3(m.xmag, m.ymag, m.zmag)
            mag = mag_fixup(mag, AHRS_ORIENTATION, COMPASS_ORIENT, COMPASS_EXTERNAL)
            gyr = Vector3(m.xgyro, m.ygyro, m.zgyro) * 0.001
            usec = m.time_usec
            if last_mag is not None and gyr.length() > radians(opts.min_rotation):
                add_errors(mag, gyr, last_mag, (usec - last_usec)*1.0e-6, total_error, rotations)
                count += 1
            last_mag = mag
            last_usec = usec

    best_i = 0
    best_err = total_error[0]
    for i in range(len(rotations)):
        r = rotations[i]
        if not r.is_90_degrees():
            continue
        if opts.verbose:
            print("%s err=%.2f" % (r, total_error[i]/count))
        if total_error[i] < best_err:
            best_i = i
            best_err = total_error[i]
    r = rotations[best_i]
    print("Current rotation is AHRS_ORIENTATION=%s COMPASS_ORIENT=%s COMPASS_EXTERNAL=%u" % (
        rotations[AHRS_ORIENTATION],
        rotations[COMPASS_ORIENT],
        COMPASS_EXTERNAL))
    print("Best rotation is %s err=%.2f from %u points" % (r, best_err/count, count))
    print("Please set AHRS_ORIENTATION=%s COMPASS_ORIENT=%s COMPASS_EXTERNAL=1" % (
        rotations[AHRS_ORIENTATION],
        rotations[COMPASS_ORIENT]))

for filename in args:
    magfit(filename)