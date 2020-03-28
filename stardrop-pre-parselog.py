#!/usr/bin/env python3
# coding: utf-8
import re, datetime, argparse, sys
import pandas as pd

class Reader(object):

    def __init__(self, g):
        self.g = g
    def read(self, n=0):
        try:
            return next(self.g)
        except StopIteration:
            return ''

def log_parse(original_log):

    grabbag = ['License_released', 'License_granted', 'Purging_license', 'License_refused']

    for line in original_log:
        data = re.split("#", line.strip('\n'))
        data[0] = data[0][12:]  #LOG:stuffffUSERNAME username occurs 12 chars

        if [i for i in grabbag if(i in data[1])]:        
            pass
        else:
            continue

        yield data

def cmd_args(args=None):
    parser = argparse.ArgumentParser("Prepares flexlm log for datamining.")

    parser.add_argument('filename',
                    help='path/filename of logfile to file to parse')

    parser.add_argument('-s', '--start',  dest='start',
                    help='Start date  of the log YYYY-MM-DD')

    opt = parser.parse_args(args)
    return opt

def main(args=None):
    opt = cmd_args(args)
    kwargs = {}

    if (opt.start):
       current_date = opt.start
       kwargs = {'start': current_date}

    if (opt.filename):
        outfile_name = opt.filename+"-min"
        #print('Output file:',outfile_name)

    with open(opt.filename, 'rt', encoding='utf-8', errors='ignore')as f:
        original_log = f.readlines()
        lines_we_keep = list(log_parse(original_log))
        df = pd.DataFrame.from_records(lines_we_keep, columns=['User','Action','Number', 'Date'])
        df['Date']  = pd.to_datetime(df['Date'])
        
        #[print(i) for i in lines_we_keep]
        with pd.option_context('display.max_rows', None, 'display.max_columns', None):
            #df = df.loc[df['Action'] == 'License_refused']
            # Set index
            df = df.set_index(df['Date'])

            # Select observations between two datetimes
            print(df.loc['2020-02-01 01:00:00':'2020-03-01 04:00:00'])
            #print(df)
            print(df.User.unique())

    sys.exit(1)

if __name__ == '__main__':
    try:
        main(sys.argv[1:])
    except ValueError:
        print("Give me something to do")
        sys.exit(1)
