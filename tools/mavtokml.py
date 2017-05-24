#!/usr/bin/env python

'''
example program to extract GPS data from a mavlink log, and create a GPX
file, for loading into google earth
'''
from __future__ import print_function

import time
import simplekml
import math
from simplekml import Kml, Snippet, Types

from argparse import ArgumentParser
parser = ArgumentParser(description=__doc__)
parser.add_argument("--condition", default=None, help="select packets by a condition")
parser.add_argument("--nofixcheck", default=False, action='store_true', help="don't check for GPS fix")
parser.add_argument("logs", metavar="LOG", nargs="+")
args = parser.parse_args()

from pymavlink import mavutil


def mav_to_kml(infilename, outfilename):
    '''convert a mavlink log file to a GPX file'''

    mlog = mavutil.mavlink_connection(infilename)
    kml=simplekml.Kml()
   # outf = open(outfilename, mode='w')



    timestamps = []
    coordinates = []
    angles = []


    def process_packet(timestamp, lat, lon, alt, hdg, v, roll, pitch, yaw):
        t = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.localtime(timestamp)) 
        timestamps.append(t)
        coordinates.append([lon,lat,alt])
        #Unsure of angles on this - pitch and roll may be reveresed
        angles.append([yaw,pitch,roll])


    count=0
    lat=0
    lon=0
    fix=0
    roll=0
    pitch=0
    yaw=0
    while True:
        m = mlog.recv_match(type=['GPS_RAW', 'GPS_RAW_INT', 'GPS', 'GPS2', 'ATTITUDE', 'ATT'], condition=args.condition)
        if m is None:
            break
        if m.get_type() == 'GPS_RAW_INT':
            lat = m.lat/1.0e7
            lon = m.lon/1.0e7
            alt = m.alt/1.0e3
            v = m.vel/100.0
            hdg = m.cog/100.0
            timestamp = m._timestamp
            fix = m.fix_type
        elif m.get_type() == 'GPS_RAW':
            lat = m.lat
            lon = m.lon
            alt = m.alt
            v = m.v
            hdg = m.hdg
            timestamp = m._timestamp
            fix = m.fix_type
        elif m.get_type() == 'GPS' or m.get_type() == 'GPS2':
            lat = m.Lat
            lon = m.Lng
            alt = m.Alt
            v = m.Spd
            hdg = m.GCrs
            timestamp = m._timestamp
            fix = m.Status

        #Attitude information from mavlink file, is not present in BIN
        elif m.get_type() == 'ATTITUDE':
            roll=math.degrees(m.roll)
            pitch=math.degrees(m.pitch)
            yaw=math.degrees(m.yaw)
            timestamp = m._timestamp
            #continue #can remove this to get every attitude update
        #Attitude information from .bin file
        elif m.get_type() == 'ATT':
            roll=math.degrees(m.Roll)
            pitch=math.degrees(m.Pitch)
            yaw=m.Yaw
            timestamp = m._timestamp
            #continue #can remove this to get every attitude update
        else:
            pass

        if fix < 2 and not args.nofixcheck:
            continue
        if lat == 0.0 or lon == 0.0:
            continue
        process_packet(timestamp, lat, lon, alt, hdg, v, roll, pitch, yaw)
        count += 1


    # Create the KML document
    kml = Kml(name="Tracks", open=1)
    doc = kml.newdocument(name='GPS device', snippet=Snippet('Created ' + timestamps[0]))
    doc.lookat.gxtimespan.begin = timestamps[0]
    doc.lookat.gxtimespan.end = timestamps[-1]
    doc.lookat.longitude = coordinates[0][0]
    doc.lookat.latitude = coordinates[0][1]
    doc.lookat.range = 500

    # Create a folder
    fol = doc.newfolder(name='Tracks')

    # Create a model
    #quadmodel = simpleKml.newModel()

    # Create a schema for extended data: heart rate, cadence and power
    #schema = kml.newschema()
    #schema.newgxsimplearrayfield(name='heartrate', type=Types.int, displayname='Heart Rate')
    #schema.newgxsimplearrayfield(name='cadence', type=Types.int, displayname='Cadence')
    #schema.newgxsimplearrayfield(name='power', type=Types.float, displayname='Power')

    # Create a new track in the folder
    trk = fol.newgxtrack(name=timestamps[0])
    trk.altitudemode = simplekml.AltitudeMode.absolute
    
    # Apply the above schema to this track
    #trk.extendeddata.schemadata.schemaurl = schema.id

    # Add all the information to the track
    trk.newwhen(timestamps) # Each item in the give nlist will become a new <when> tag
    trk.newgxcoord(coordinates) # Ditto
    trk.newgxangle(angles)
    #trk.extendeddata.schemadata.newgxsimplearraydata('heartrate', heartrate) # Ditto
    #trk.extendeddata.schemadata.newgxsimplearraydata('cadence', cadence) # Ditto
    #trk.extendeddata.schemadata.newgxsimplearraydata('power', power) # Ditto

    # Styling
    trk.stylemap.normalstyle.iconstyle.icon.href = 'http://earth.google.com/images/kml-icons/track-directional/track-0.png'
    trk.stylemap.normalstyle.linestyle.color = '99ffac59'
    trk.stylemap.normalstyle.linestyle.width = 6
    trk.stylemap.highlightstyle.iconstyle.icon.href = 'http://earth.google.com/images/kml-icons/track-directional/track-0.png'
    trk.stylemap.highlightstyle.iconstyle.scale = 1.2
    trk.stylemap.highlightstyle.linestyle.color = '99ffac59'
    trk.stylemap.highlightstyle.linestyle.width = 8

    # Save the kml to file
    kml.save(outfilename)

    print("Created %s with %u points" % (outfilename, count))


for infilename in args.logs:
    outfilename = infilename + '.kml'
    mav_to_kml(infilename, outfilename)
