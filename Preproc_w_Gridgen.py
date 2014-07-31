__author__ = 'aleaf'

class SFRpreproc:
    def __init__(self, SFRdata):
        self.indata = SFRdata
        ts = time.time()
        st_time = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
        self.ofp = open(os.path.join(self.indata.working_dir, 'SFR_preproc.log'), 'w')
        self.ofp.write('SFR_preproc log.')
        self.ofp.write('\n' + '#' * 25 + '\nStart Time: {0:s}\n'.format(st_time) + '#' * 25 + '\n')

    def clip_and_join_Gridgen(self, SFRoperations):

        try:
            import sys
            sys.path.append('D:/ATLData/Documents/GitHub/GIS_utils/') #path to GIS_utils repo
            import GISio

        except:
            'Could not import GIS_utils, which is required for this method.'
            quit()

        indat = self.indata

        # keep this arcpy stuff for now
        print "Clip original NHD flowlines to model domain..."
        # this creates a new file so original dataset untouched
        arcpy.Clip_analysis(indat.Flowlines_unclipped,
                            indat.MFdomain,
                            indat.Flowlines)

        print "Make a lines only version of the model domain outline..."
        arcpy.FeatureToLine_management(indat.MFdomain, indat.MFdomain[:-4] + '_outline.shp')

        # read in intersected flowlines from Gridgen, and NHD tables
        df = GISio.shp2df(indat.intersected_streams, geometry=True)
        elevs = GISio.shp2df(indat.Elevslope, index='COMID')
        pfvaa = GISio.shp2df(indat.PlusflowVAA, index='COMID')

        # check for MultiLineStrings and drop them (these are features that were fragmented by the boundaries)
        mls = [i for i in df.index if 'multi' in df.ix[i]['geometry'].type.lower()]
        mlsdf = df.ix[mls]
        self.ofp.write('Deleted MultiLineStrings associated with these COMIDs:\n'
                       '(most likely are features that were fragmented by the grid boundaries)\n')
        self.ofp.write(mls.to_string(columns=['COMID'])) # right these dataframe column to log file
        df = df.drop(mls, axis=0)

        # delete all unneeded fields
        fields2keep = ["comid",
                     "divergence",
                     "lengthkm",
                     "thinnercod",
                     "maxelevsmo",
                     "minelevsmo",
                     "hydroseq",
                     "uphydroseq",
                     "dnhydroseq",
                     "reachcode",
                     "streamorde",
                     "arbolatesu",
                     "fcode",
                     "levelpathI",
                     "uplevelpat",
                     "dnlevelpat"]
        fields2keep = [x.lower() for x in fields2keep]
        fields2delete = [f.lower() for f in pfvaa.columns + elevs.columns if f.lower() != 'oid' and
                                                                             f.lower() not in fields2keep]
        self.ofp.write('Joining {0:s} with {1:s}: fields kept:\n'.format(indat.Elevslope, indat.intersected_streams))
        self.ofp.write('%s\n' % ('\n'.join(fields2keep)))
        self.ofp.write('deleted:\n')
        self.ofp.write('%s\n' % ('\n'.join(fields2delete)))

        print "joining PlusflowVAA and Elevslope tables to NHD Flowlines..."
        lsuffix = 'fl'
        df = df.join(elevs, on='COMID', lsuffix='', rsuffix='1')
        df = df.join(pfvaa, on='COMID', lsuffix='', rsuffix='1')

        self.ofp.write('\n' + 25*'#' + '\nRemoving COMIDs with no elevation information, and with ThinnerCod = -9..\n')
        print "Removing COMIDs with no elevation information, and with ThinnerCod = -9..."

        # drop inactive cells
        df = df[df.nodenumber != -1.0]

        # drop reaches with no elevation information
        no_elev = df[(df.MAXELEVSMO == 0) | (df.MAXELEVSMO == -9998)]
        self.ofp.write(no_elev.to_string(columns=['COMID', 'MAXELEVSMO'])) # right these dataframe column to log file
        df = df.drop(no_elev.index, axis=0)
        print "removed %d with no elevation data".format(len(no_elev))

        # drop reaches with ThinnerCod = -9
        tc9 = df[df.ThinnerCod == -9]
        self.ofp.write(tc9.to_string(columns=['COMID', 'ThinnerCod'])) # right these dataframe column to log file
        df = df.drop(tc9.index, axis=0)
        print "removed %d with ThinnerCod=-9".format(len(tc9))

        print "Adding in start,end x,y and lengths..."
        df['X_start'] = [g.xy[0][0] for g in df.geometry]
        df['X_end'] = [g.xy[0][-1] for g in df.geometry]
        df['Y_start'] = [g.xy[1][0] for g in df.geometry]
        df['Y_end'] = [g.xy[1][-1] for g in df.geometry]
        df['LengthFt'] = [g.length for g in df.geometry]

        print "\nRemoving stream fragments with lengths less than or equal to %s..." % indat.reach_cutoff
        cutoff = df[df.LengthFt <= 1.0]
        self.ofp.write(cutoff.to_string(columns=['COMID', indat.node_attribute, 'LengthFt']))
        df = df.drop(cutoff.index, axis=0)
        print "removed %d fragments".format(len(cutoff))

        print "creating Fragment IDs (proto-reaches)"
        df['FragID'] = range(len(df))

        # write output to shapefile
        GISio.df2shp(df, indat.intersect, prj=indat.Flowlines[:-4]+'.prj')

        print "Done with pre-processing, ready to run intersect!"
        self.ofp.write('\n' + '#' * 25 + '\nDone with pre-processing, ready to run intersect!')
        ts = time.time()
        end_time = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')

        self.ofp.write('\n' + '#' * 25 + '\nEnd Time: %s\n' % end_time + '#' * 25)
        self.ofp.close()


