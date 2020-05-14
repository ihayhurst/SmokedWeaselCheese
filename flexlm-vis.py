#!/usr/bin/env python3
# coding: utf-8
"""Parse Optibrium Geneious Flexlm style log file.
   Show graphics of useage and availability of license """
import re
import argparse
import sys
import json
import time
import datetime
import functools
import pandas as pd
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
from matplotlib.dates import date2num
import seaborn as sns

# Req for ldap3 wrapper to real names for userID inside corporate LAN
# import ADlookup as ad
# Set ISO 8601 Datetime format e.g. 2020-12-22T14:30
DT_FORMAT = '%Y-%m-%dT%H:%M'


def log_parse(original_log, **kwargs):
    """Take logfile and add date to every time.
    Keep only the events weare interested in"""
    if kwargs.get('hint'):
        current_date = datetime.date.fromisoformat(kwargs.get('hint'))
        for line in original_log:
            data = line.split()
            try:
                if len(data) > 3:
                    pass
            except IndexError:
                continue

            try:
                # Do we have a TIMESTAMP, if we do and it's newer then use it
                if data[2] == "TIMESTAMP":
                    new_date = datetime.datetime.strptime(data[3], "%m/%d/%Y").date()
                    # If it hasn't changed then value of current_date is OK
                    if new_date == current_date:
                        pass
                    else:
                        # if it has changed, then that's the new value of current_date
                        current_date = new_date
                        continue
            except IndexError:
                continue

            grabbag = ['IN:', 'OUT:', 'DENIED:', 'QUEUED:', 'DEQUEUED:']
            if [i for i in grabbag if i in data[2]]:
                if re.findall("lmgrd", data[1]):
                    continue # skip flexlm housekeeping
                if re.findall("SUITE.*|MSI.*|License_Holder", data[3]):
                    continue # skip the Token Library
              
                record_date = current_date.strftime("%Y-%m-%d")
                data = f'{record_date} ' + " ".join(re.split(r'\s+|@|\.', line))
                data = data.split(maxsplit=7)
            else:
                continue

            yield data


def readfile_to_dataframe(**kwargs):
    """Read in file, return dataframe"""
    filename = kwargs.get('filename')
    with open(filename, 'rt', encoding='utf-8', errors='ignore')as f:
        original_log = f.readlines()
        lines_we_keep = list(log_parse(original_log, **kwargs))
        columns_read = ['Date', 'Time', 'Product', 'Action', 'Module', 'User', 'Host', 'State']
        discard_cols = ['Time', 'Product', 'Host', 'State']
        df = pd.DataFrame.from_records(lines_we_keep, columns=columns_read)
        df['Date'] = pd.to_datetime(df['Date'] + ' ' + df['Time'])
        df.drop(list(discard_cols), axis=1, inplace=True)
        df = df.set_index(df['Date'])
    return df


def graph(events, df_sub_ref):
    """Draw graph of license use duration per user on timeline
        plot time license unavailable as red x"""
    color_labels = events.Module.unique()
    rgb_values = sns.color_palette("Paired", len(color_labels))
    color_map = dict(zip(color_labels, rgb_values))
    fig, ax = plt.subplots(figsize=(16, 10))
    ax.tick_params(axis='both', which='major', labelsize=6)
    ax.tick_params(axis='both', which='minor', labelsize=6)
    labels = events['User']
    fig.autofmt_xdate()
    ax.xaxis_date()
    patches = [ plt.plot([],[], marker="o", ms=10, ls="", mec=None, color=rgb_values[i], 
            label="{:s}".format(color_labels[i]) )[0]  for i in range(len(color_labels))]
    ax.hlines(labels, date2num(events.LicOut),date2num(events.LicIn),
              linewidth=10, colors=events.Module.map(color_map))
    plt.legend(handles=patches, bbox_to_anchor=(0, 1), loc='upper left')

    bx = plt.plot(date2num(df_sub_ref.Date), df_sub_ref.User, 'rx')
    fig.tight_layout()
    plt.show()


@functools.lru_cache(maxsize=128, typed=False)
def simple_user(uid):
    """ Take a user logon id and return their name """
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
    """Prepare commandline arguments return Namespace object of options set"""
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
    parser.add_argument('-a', '--Active-Directory', dest='active_directory',
                        action='store_true',
                        help='Resolve user ID to real name  in Active Directory')

    opt = parser.parse_args(args)
    return opt


def process_opts(opt):
    """Process cmdline options logic
        Calculate ROI start and end times from combinations supplied"""
    kwargs = {}
    kwargs = {'filename': opt.filename, **kwargs}

    if opt.dur:
        # If set get timedelta it represents
        duration = parse_duration(opt.dur)
        print(f'Duration {opt.dur}')

    if opt.dur and opt.start and opt.end:
        # Assume start and range ignore end
        opt.end_dt = date_to_dt(opt.start, DT_FORMAT) + duration
        opt.end = opt.end_dt.strftime(DT_FORMAT)

    if opt.dur and opt.start and not opt.end:
        # Start and range
        opt.end_dt = date_to_dt(opt.start, DT_FORMAT) + duration
        opt.end = opt.end_dt.strftime(DT_FORMAT)

    if opt.dur and not opt.start and opt.end:
        # Range before enddate
        opt.start_dt = date_to_dt(opt.end, DT_FORMAT) - duration
        opt.start = opt.start_dt.strftime(DT_FORMAT)

        # This won't return the full duration until we know the end date in our log
    if opt.dur and not opt.start and not opt.end:
        # End of log back by duration
        opt.end_dt = datetime.datetime.now()
        opt.end = dt_to_date(opt.end_dt, DT_FORMAT)
        opt.start_dt = date_to_dt(opt.end, DT_FORMAT) - duration
        opt.start = opt.start_dt.strftime(DT_FORMAT)

    if not opt.dur and opt.start and opt.end:
        # Date range
        if date_to_dt(opt.start, DT_FORMAT) > date_to_dt(opt.end, DT_FORMAT):
            # End before start so swap
            opt.start, opt.end = opt.end, opt.start

    if not opt.dur and opt.start and not opt.end:
        # Start Date only - from start date to end
        opt.end_dt = datetime.datetime.now()
        opt.end = opt.end_dt.strftime(DT_FORMAT)

    if not opt.dur and not opt.start and opt.end:
        # End Date only - from end date to start
        opt.start_dt = datetime.date(1970, 1, 1)
        opt.start = opt.start_dt.strftime(DT_FORMAT)

    if opt.hint:
        # Hint is for timestamping log before first timestsmp
        current_date = opt.hint
        kwargs = {'hint': current_date, **kwargs}

        if opt.active_directory:
            # Resolve uid to realname in Active Directory
            kwargs = {'active_directory': True, **kwargs}

    return kwargs

def parse_duration(duration):
    """Parse duration Hours,Days or Weeks Return timedelta"""
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
    """Convert date string to datetime object"""
    dateasdt = datetime.datetime.strptime(datestring, FORMAT)
    return dateasdt


def dt_to_date(dateasdt, FORMAT):
    """Convert datetime object to datestring"""
    datestring = datetime.datetime.strftime(dateasdt, FORMAT)
    return datestring


def main(args=None):
    """Main function"""
    opt = cmd_args(args)
    kwargs = process_opts(opt)
    df = readfile_to_dataframe(**kwargs)

     # Select observations between two datetimes
    if opt.start:
        df_sub = df.loc[opt.start:opt.end].copy()
    else:
        df_sub = df  # or use the whole dataset

    # Enable for AD lookup of User's real name
        if kwargs.get('active_directory'):
            df_sub['User'] = df_sub.apply(lambda row: simple_user(row.User), axis=1)

    # Unique users in time range
    print(df_sub.User.unique())

    # Split Checkout and checkin events: record refusals too
    df_sub_out = df_sub[df_sub['Action'] == 'OUT:']
    df_sub_in = df_sub[df_sub['Action'] == 'IN:']
    df_sub_ref = df_sub[df_sub['Action'] == 'DENIED:']

    # Cumulative license loan tally
    # not needed here yet

    # Events table: For every checkout get checkin; calculate the loan duration
    events = pd.DataFrame(columns=['LicOut', 'LicIn', 'Module', 'Duration', 'User'])
    t = time.process_time()
    for row in df_sub_out.itertuples():
        index = getattr(row, 'Index')
        user = getattr(row, 'User')
        out_time = getattr(row, 'Date')
        module = getattr(row, 'Module')
        # print(f'index={index} user={user}, Out Time={out_time}')
        if not len(events)%1000:
            print(f'{len(events)} : {time.process_time()- t}')

        try:
            key = ((df_sub_in.Module == module)
                   & (df_sub_in.User == user)
                   & (df_sub_in.index >= index))
            result = df_sub_in.loc[key]
            events.loc[len(events), :] = (out_time, (result.Date.iloc[0]), module,
                                          (result.Date.iloc[0] - out_time), user)
        except IndexError:
            print(f'No MATCH! {row}')
        else:
            pass

    events['LicOut'] = pd.to_datetime(events['LicOut'], utc=True)
    events['LicIn'] = pd.to_datetime(events['LicIn'], utc=True)
    events['Duration'] = pd.to_timedelta(events['Duration'])
    # Table of license refusals
    print(df_sub_ref)
    # Checkouts per module and duration
    # TODO assign colours to modules pass to graph for colour key
    print(events.groupby(['Module'])['Duration'].agg(['sum', 'count']).sort_values(['sum'], ascending=False))
    print(events)
    graph(events, df_sub_ref)


if __name__ == '__main__':
    try:
        main(sys.argv[1:])
    except ValueError:
        print("Give me something to do")
        sys.exit(1)
