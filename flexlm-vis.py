#!/usr/bin/env python3
# coding: utf-8
import re, time, datetime, argparse, sys, json
import functools
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.dates import date2num
#from datetime import datetime

#mpl.use('agg')
import ADlookup as ad

def log_parse(original_log, *args, **kwargs):

    if kwargs.get('start'):
        current_date = datetime.date.fromisoformat(kwargs.get('start'))
        for line in original_log:
            data = line.split()
            try:
                if len(data) > 3:
                    pass
            except:
                continue

            try:
                if data[2] == "TIMESTAMP": # check whether date has changed - if so, then we'll use this for each subsequent line
                    new_date = datetime.datetime.strptime(data[3], "%m/%d/%Y").date()
                    if new_date == current_date:  # if it hasn't changed then value of current_date is OK
                        pass
                    else:           #  if it has changed, then that's the new value of current_date
                        current_date = new_date
                        continue
            except IndexError:
                continue

            grabbag = ['IN:', 'OUT:', 'DENIED:', 'QUEUED:', 'DEQUEUED:']
            if [i for i in grabbag if i in data[2]]:
                if re.findall("lmgrd", data[1]):
                    continue # skip flexlm housekeeping 
                elif re.findall("SUITE.*|MSI.*|License_Holder", data[3]):
                    continue # skip the Token Library

                data = current_date.strftime("%Y-%m-%d") + " " + " ".join(re.split('\s+|@|\.', line))
                data = data.split(maxsplit=7)
            else:
                continue
            yield data


def graph(events, df_sub_ref):
    fig, ax = plt.subplots(figsize=(16, 10))
    ax.tick_params(axis='both', which='major', labelsize=6)
    ax.tick_params(axis='both', which='minor', labelsize=6)
    labels = events['User']
    ax = ax.xaxis_date()
    ax = plt.hlines(labels, date2num(events.LicOut), date2num(events.LicIn), linewidth=6, color='blue')
    ax = plt.plot(date2num(df_sub_ref.Date), df_sub_ref.User, 'rx')
    fig.autofmt_xdate()
    plt.show()
    return


@functools.lru_cache(maxsize=128, typed=False)
def simpleUser(uid):
    test1 = ad.AD()
    try:
        identity = test1.fetch(f'(sAMAccountName={uid})', 'displayName')
    except IndexError:
        # User Not Found, return the original uid
        return uid
    identity = json.loads(identity)
    identity = identity["attributes"]["displayName"][0]
    return identity


def cmd_args(args=None):
    parser = argparse.ArgumentParser("Prepares flexlm log for datamining.")

    parser.add_argument('filename',
                        help='path/filename of gzipped logfile to file to parse')

    parser.add_argument('-s', '--start', dest='start',
                        help='Start date  of the log YYYY-MM-DD')

    opt = parser.parse_args(args)
    return opt


def main(args=None):
    opt = cmd_args(args)
    kwargs = {}

    if  opt.start:
        current_date = opt.start
        kwargs = {'start': current_date}

    if opt.filename:
        outfile_name = opt.filename+"-min"
        #print('Output file:',outfile_name)

    with open(opt.filename, 'rt', encoding='utf-8', errors='ignore')as f:
        original_log = f.readlines()
        lines_we_keep = list(log_parse(original_log, *args, **kwargs))
        columnsRead = ['Date', 'Time', 'Product', 'Action', 'Module', 'User', 'Host', 'State']
        discard_cols = ['Time', 'Product', 'Host', 'State']
        df = pd.DataFrame.from_records(lines_we_keep, columns=columnsRead)
        df['Date'] = pd.to_datetime(df['Date'] + ' ' + df['Time'])
        df.drop([x for x in discard_cols], axis=1, inplace=True)

        df = df.set_index(df['Date'])
        print(df[df['Action'] == 'DENIED:'])
        # Select observations between two datetimes
        #df_sub=(df.loc['2019-01-01 00:00:00':'2020-01-31 23:59:59'])
        df_sub = df #or use the whole dataset

        #Enable for AD lookup of User's real name
        df_sub['User'] = df_sub.apply(lambda row: simpleUser(row.User), axis=1)

        #Unique users in time range
        print(df_sub.User.unique())

        #Split Checkout and checkin events: record refusals too
        df_sub_out = df_sub[df_sub['Action'] == 'OUT:']
        df_sub_in = df_sub[df_sub['Action'] == 'IN:']
        df_sub_ref = df_sub[df_sub['Action'] == 'DENIED:']

        #Create an events table: For every checkout find a later checkin and calculate the loan duration
        events = pd.DataFrame(columns=['LicOut', 'LicIn', 'Module', 'Duration', 'User'])
        t = time.process_time()
        for row in df_sub_out.itertuples():
            index = getattr(row, 'Index')
            user = getattr(row, 'User')
            OutTime = getattr(row, 'Date')
            module = getattr(row, 'Module')
            #print(f'index={index} user={user}, OutTime={OutTime}')
            if not(len(events)%1000):
                print(len(events),':',time.process_time()- t)

            try:
                key = ((df_sub_in.Module == module) & (df_sub_in.User == user) & (df_sub_in.index >= index))
                result = df_sub_in.loc[key]
                events.loc[len(events), :] = (OutTime, (result['Date'].iloc[0]), module, (result['Date'].iloc[0]- OutTime), user)
            except IndexError:
                print(f'No MATCH! {row}')
            else:
                pass

        events['LicOut'] = pd.to_datetime(events['LicOut'], utc=True)
        events['LicIn'] = pd.to_datetime(events['LicIn'], utc=True)
        events['Duration'] = pd.to_timedelta(events['Duration'])
        print(df_sub_ref)
        # Checkouts per module and duration
        print(events.groupby(['Module'])['Duration'].agg(['sum', 'count']).sort_values(['sum'], ascending=False))
        print(events)
        graph(events, df_sub_ref)


    sys.exit(1)

if __name__ == '__main__':
    try:
        main(sys.argv[1:])
    except ValueError:
        print("Give me something to do")
        sys.exit(1)
