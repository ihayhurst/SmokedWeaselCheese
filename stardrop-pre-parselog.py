#!/usr/bin/env python3
# coding: utf-8
import re, datetime, argparse, sys, json
import functools
import pandas as pd
import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.dates import date2num
from datetime import datetime

#Req for ldap3 wrapper to real names for userID inside corporate LAN
#import ADlookup as ad


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


def graph(events,df_sub_ref):
    print(events)
    fig, ax = plt.subplots(figsize=(16, 9))
    ax.tick_params(axis='both', which='major', labelsize=10)
    ax.tick_params(axis='both', which='minor', labelsize=8)
    labels = events['User']
    ax = ax.xaxis_date()
    ax = plt.hlines(labels, date2num(events.LicOut), date2num(events.LicIn), linewidth=10, color='blue')
    ax = plt.plot(date2num(df_sub_ref.Date), df_sub_ref.User, 'rx')
    fig.autofmt_xdate()
    plt.show()
    return


@functools.lru_cache(maxsize=128, typed=False)
def simpleUser (uid):
    test1 = ad.AD()
    try:
        identity = test1.fetch(f'(sAMAccountName={uid})', 'displayName' )
    except IndexError:
        return('User Not Found')
    identity = json.loads(identity)
    identity = identity["attributes"]["displayName"][0]
    return identity


def cmd_args(args=None):
    parser = argparse.ArgumentParser("Prepares flexlm log for datamining.")

    parser.add_argument('filename',
                    help='path/filename of gzipped logfile to file to parse')

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
        
        with pd.option_context('display.max_rows', None, 'display.max_columns', None):
            #df = df.loc[df['Action'] == 'License_refused']

            # Set index
            pass

        df = df.set_index(df['Date'])

        # Select observations between two datetimes
        #df_sub=(df.loc['2020-03-14 07:00:00':'2020-04-14 10:00:00'])
        df_sub = df #or use the whole dataset

        #Enable for AD lookup of User's real name
        #df_sub['User'] = df_sub.apply(lambda row: simpleUser(row.User), axis= 1)

        #Unique users in time range
        print(df_sub.User.unique())

        #Split Checkout and checkin events: record refusals too
        df_sub_out = df_sub[df_sub['Action'] == 'License_granted']
        df_sub_in = df_sub[df_sub['Action'] == 'License_released']
        df_sub_ref = df_sub[df_sub['Action'] == 'License_refused']

        #Create an events table: For every checkout find a later checkin and calculate the loan duration
        events = pd.DataFrame(columns=['LicOut','LicIn', 'Duration', 'User'])
        for index, row in df_sub_out.iterrows():
            user = row['User']
            OutTime = row['Date']
            try:
                key = ((df_sub_in.User == user) & (df_sub_in.index >= index))
                result = df_sub_in.loc[key]
                events.loc[len(events), :] = (OutTime, (result['Date'].iloc[0]), (result['Date'].iloc[0]- OutTime),  user)
            except:
                print (f'No MATCH! {row}')
            else:
                pass

        events['LicOut'] = pd.to_datetime(events['LicOut'], utc=True)
        events['LicIn'] = pd.to_datetime(events['LicIn'], utc=True)
        events['Duration'] = pd.to_timedelta(events['Duration'])
        print(df_sub_ref)
        graph(events,df_sub_ref)


    sys.exit(1)

if __name__ == '__main__':
    try:
        main(sys.argv[1:])
    except ValueError:
        print("Give me something to do")
        sys.exit(1)
