#!/usr/bin/env python3
# coding: utf-8
import re
import argparse
import sys
import json
import datetime
import functools
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.dates import date2num

#import ADlookup as ad
DT_FORMAT = '%Y-%m-%dT%H:%M'

def log_parse(original_log, *args, **kwargs):

    if kwargs.get('hint'):
        current_date = datetime.date.fromisoformat(kwargs.get('hint'))
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
                    continue # skip  flexlm housekeeping

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
    parser = argparse.ArgumentParser("Prepares license log for datamining.")

    parser.add_argument('filename',
                        help='path/filename of logfile to file to parse')

    parser.add_argument('-i', '--hint', dest='hint',
                        help='Hint start date of the log YYYY-MM-DD')

    parser.add_argument('-s', '--start', dest='start',
                        help='Start date YYYY-MM-DDTHH:MM e.g 2020-03-23T13:24')
    parser.add_argument('-e', '--end', dest='end',
                        help='End   date YYYY-MM-DDTHH:MM')
    parser.add_argument('-d', '--dur', dest='dur',
                        help='Duration: Hours, Days, Weeks,  e.g. 2W for 2 weeks')

    opt = parser.parse_args(args)

    return opt


def parse_duration(duration):
    hours = datetime.timedelta(hours=1)
    days = datetime.timedelta(days=1)
    weeks = datetime.timedelta(weeks=1)
    fields = re.split(r'(\d+)', duration)
    duration = int(fields[1])
    if fields[2][:1].upper() == 'H':
        duration_td = duration * hours
    elif fields[2][:1].upper() == 'D':
        duration_td = duration * days
    elif fields[2][:1].upper() == 'W':
        duration_td = duration * weeks
    else:
        raise ValueError

    return duration_td


def date_to_dt(datestring, FORMAT):
    dateasdt = datetime.datetime.strptime(datestring, FORMAT)
    return dateasdt


def dt_to_date(dateasdt, FORMAT):
    datestring = datetime.datetime.strftime(dateasdt, FORMAT)
    return datestring


def main(args=None):
    opt = cmd_args(args)
    kwargs = {}

    if opt.dur and opt.start and opt.end:  # Assume start and range ignore end
        print("All three madness")  # Debug
        print("Duration", opt.dur)
        duration = parse_duration(opt.dur)
        opt.end_dt = date_to_dt(opt.start, DT_FORMAT)+duration
        opt.end = opt.end_dt.strftime(DT_FORMAT)

    if opt.dur and opt.start and not opt.end:  # Start and range
        print("Start date and duration")  # Debug
        print("Duration", opt.dur)
        duration = parse_duration(opt.dur)
        opt.end_dt = date_to_dt(opt.start, DT_FORMAT) + duration
        opt.end = opt.end_dt.strftime(DT_FORMAT)

    if opt.dur and not opt.start and opt.end:  # Range before enddate
        print("End date and duration")  # Debug
        duration = parse_duration(opt.dur)
        opt.start_dt = date_to_dt(opt.end, DT_FORMAT) - duration
        opt.start = opt.start_dt.strftime(DT_FORMAT)

    if opt.dur and not opt.start and not opt.end:  # tailmode with range
        print("End of log back by duratiion")  # Debug
        duration = parse_duration(opt.dur)
        opt.end_dt = datetime.datetime.now()
        opt.end = dt_to_date(opt.end_dt, DT_FORMAT)
        opt.start_dt = date_to_dt(opt.end, DT_FORMAT) - duration
        opt.start = opt.start_dt.strftime(DT_FORMAT)

    if not opt.dur and opt.start and opt.end:  # Date range
        print("Start date and end date")  # Debug
        if date_to_dt(opt.start, DT_FORMAT) > date_to_dt(opt.end, DT_FORMAT):  # End before start so swap
            opt.start, opt.end = opt.end, opt.start

    if not opt.dur and opt.start and not opt.end:  # Start Date only - from start date to end
        print("Start Date to end of log ")  # Debug
        opt.end_dt = datetime.datetime.now()
        opt.end = opt.end_dt.strftime(DT_FORMAT)

    if not opt.dur and not opt.start and opt.end:  # End Date only - from end date to start
        print("End date back to the dawn of time (or the log at least) ")  # Debug
        opt.start_dt = datetime.date(1970, 1, 1)
        opt.start = opt.start_dt.strftime(DT_FORMAT)

    if  opt.hint:
        current_date = opt.hint
        kwargs = {'hint': current_date}

    if not opt.start:
        kwargs = {'from_date': opt.start, 'to_date': opt.end, **kwargs}

    with open(opt.filename, 'rt', encoding='utf-8', errors='ignore')as f:
        original_log = f.readlines()
        lines_we_keep = list(log_parse(original_log, *args, **kwargs))
        columnsRead = ['Date', 'Time', 'Product', 'Action', 'Module', 'User', 'Host', 'State']
        discard_cols = ['Time', 'Product', 'Module', 'Host', 'State']
        df = pd.DataFrame.from_records(lines_we_keep, columns=columnsRead)
        df['Date'] = pd.to_datetime(df['Date'] + ' ' + df['Time'])
        df.drop([x for x in discard_cols], axis=1, inplace=True)

        df = df.set_index(df['Date'])

        # Select observations between two datetimes
        if opt.start:
            df_sub=(df.loc[opt.start : opt.end])
        else:
            df_sub = df #or use the whole dataset

        #Enable for AD lookup of User's real name
        #df_sub['User'] = df_sub.apply(lambda row: simpleUser(row.User), axis=1)

        # Unique users in time range
        print(df_sub.User.unique())

        # Split Checkout and checkin events: record refusals too
        df_sub_out = df_sub[df_sub['Action'] == 'OUT:']
        df_sub_in = df_sub[df_sub['Action'] == 'IN:']
        df_sub_ref = df_sub[df_sub['Action'] == 'DENIED:']

        # events table: For every checkout get checkin; calculate the loan duration
        events = pd.DataFrame(columns=['LicOut', 'LicIn', 'Duration', 'User'])
        for index, row in df_sub_out.iterrows():
            user = row['User']
            OutTime = row['Date']
            try:
                key = ((df_sub_in.User == user) & (df_sub_in.index >= index))
                result = df_sub_in.loc[key]
                events.loc[len(events), :] = (OutTime, (result.Date.iloc[0]),
                                              (result.Date.iloc[0] - OutTime), user)
            except IndexError:
                print(f'No MATCH! {row}')
            else:
                pass

        events['LicOut'] = pd.to_datetime(events['LicOut'], utc=True)
        events['LicIn'] = pd.to_datetime(events['LicIn'], utc=True)
        events['Duration'] = pd.to_timedelta(events['Duration'])
        print(df_sub_ref)
        graph(events, df_sub_ref)


    sys.exit(1)

if __name__ == '__main__':
    try:
        main(sys.argv[1:])
    except ValueError:
        print("Give me something to do")
        sys.exit(1)
